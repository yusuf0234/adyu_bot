"""
logger.py – SQLite-based interaction logger for AdyuBot v3.0
Optimizations over v2.4:
  - Periodic WAL checkpoint (every 100 writes) prevents unbounded WAL growth
  - purge_old_logs() removes entries older than 30 days
  - Thread-local connection pool retained
  - WAL mode + NORMAL sync retained for best write performance
"""

import sqlite3
import os
import threading
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), 'chat_logs.db')

# ── Thread-local connection pool ───────────────────────────────────────────────
_local = threading.local()

def _get_conn() -> sqlite3.Connection:
    """Return a per-thread cached SQLite connection (creates if missing)."""
    if not getattr(_local, "conn", None):
        conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")    # better concurrent writes
        conn.execute("PRAGMA synchronous=NORMAL")  # safe + faster than FULL
        conn.execute("PRAGMA cache_size=-8000")    # 8 MB page cache per thread
        _local.conn = conn
    return _local.conn


def _close_conn():
    """Close the thread-local connection (call on thread exit if needed)."""
    if getattr(_local, "conn", None):
        try:
            _local.conn.close()
        except Exception:
            pass
        _local.conn = None


# ── Init guard ─────────────────────────────────────────────────────────────────
_initialized = False
_init_lock   = threading.Lock()

def init_db():
    """Create tables and indexes. Safe to call multiple times (idempotent)."""
    global _initialized
    with _init_lock:
        if _initialized:
            return
        conn = _get_conn()
        conn.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT NOT NULL,
                question    TEXT,
                sources     TEXT,
                response    TEXT,
                source_type TEXT
            )
        ''')
        # Index for fast DESC queries (admin /logs endpoint)
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_logs_id_desc ON logs (id DESC)
        ''')
        # Schema migrations (idempotent)
        for col in ("sources", "source_type"):
            try:
                conn.execute(f"ALTER TABLE logs ADD COLUMN {col} TEXT")
            except Exception:
                pass  # already exists
        conn.commit()
        _initialized = True


# ── WAL checkpoint counter ───────────────────────────────────────────────────────────
_write_counter = 0
_write_lock    = threading.Lock()
WAL_CHECKPOINT_EVERY = 100  # run PRAGMA wal_checkpoint(TRUNCATE) every N writes


def _maybe_checkpoint(conn: sqlite3.Connection):
    """Periodically truncate the WAL file to prevent unbounded growth."""
    global _write_counter
    with _write_lock:
        _write_counter += 1
        do_checkpoint = (_write_counter % WAL_CHECKPOINT_EVERY == 0)
    if do_checkpoint:
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            print(f"[logger] WAL checkpoint run (write #{_write_counter}).")
        except Exception as e:
            print(f"[logger] WAL checkpoint error: {e}")


def log_interaction(question: str, sources: str, response: str, source_type: str = "web"):
    """
    Persist a chat interaction.
    *sources*   – comma-separated URLs (not full context text).
    *response*  – truncated to 2000 chars to keep DB lean.
    """
    try:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO logs (timestamp, question, sources, response, source_type) "
            "VALUES (?, ?, ?, ?, ?)",
            (datetime.now().isoformat(), question, sources, response[:2000], source_type),
        )
        conn.commit()
        _maybe_checkpoint(conn)
    except Exception as e:
        print(f"[logger] Log write error: {e}")
        # Reset broken connection so next call gets a fresh one
        _close_conn()


def purge_old_logs(days: int = 30) -> int:
    """
    Delete log entries older than *days* days.
    Returns number of rows deleted.
    """
    try:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        conn = _get_conn()
        cur = conn.execute("DELETE FROM logs WHERE timestamp < ?", (cutoff,))
        conn.commit()
        deleted = cur.rowcount
        if deleted:
            print(f"[logger] Purged {deleted} log entries older than {days} days.")
        return deleted
    except Exception as e:
        print(f"[logger] Log purge error: {e}")
        _close_conn()
        return 0


def get_recent_logs(limit: int = 50) -> list[dict]:
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT timestamp, question, response, source_type "
            "FROM logs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {"timestamp": r[0], "question": r[1], "response": r[2], "source_type": r[3]}
            for r in rows
        ]
    except Exception as e:
        print(f"[logger] Log read error: {e}")
        _close_conn()
        return []


# Initialize on import (fast — guarded by _initialized flag)
init_db()
