"""
main.py – FastAPI backend for AdyuBot v3.0.0
Optimizations over v2.4:
  - Cache hit/miss counters exposed in /health and /admin/stats
  - Uptime tracking
  - Weekly log purge job (purge_old_logs)
  - Thread-safe SimpleCache with RLock (unchanged)
  - Thread-safe rate limiter with Lock (unchanged)
"""

import os
import time
import asyncio
import threading
from collections import OrderedDict, defaultdict
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks, Header, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional

load_dotenv()

from vector_store import vector_store
from scraper import scrape_site
from llm import generate_answer_stream, check_forbidden_topics, MAX_QUESTION_LEN
from logger import log_interaction, get_recent_logs, init_db

# ── Config ─────────────────────────────────────────────────────────────────────
FRONTEND_URL  = os.getenv("FRONTEND_URL", "*")
ADMIN_TOKEN   = os.getenv("ADMIN_TOKEN", "default_secret")
RATE_LIMIT    = int(os.getenv("RATE_LIMIT", "10"))       # max requests per window
RATE_WINDOW   = int(os.getenv("RATE_WINDOW", "60"))      # seconds
CACHE_TTL     = int(os.getenv("CACHE_TTL", "3600"))      # seconds
CACHE_CAP     = int(os.getenv("CACHE_CAPACITY", "300"))  # max cache entries

# ── Startup time ───────────────────────────────────────────────────────────────
_startup_time = time.time()

# ── Lifespan ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[AdyuBot] Starting up…")

    # Initialize DB safely
    try:
        init_db()
        print("[AdyuBot] Database initialized.")
    except Exception as e:
        print(f"[AdyuBot] WARNING: DB init failed: {e}")

    # Start schedulers inside lifespan (avoids double-start on hot reload)
    from apscheduler.schedulers.background import BackgroundScheduler
    from logger import purge_old_logs
    scheduler = BackgroundScheduler(timezone="Europe/Istanbul")
    scheduler.add_job(
        func=_background_crawl,
        trigger="interval",
        days=7,
        id="weekly_crawl",
        replace_existing=True,
    )
    scheduler.add_job(
        func=purge_old_logs,
        trigger="interval",
        days=7,
        id="weekly_log_purge",
        replace_existing=True,
    )
    scheduler.start()
    print("[AdyuBot] Scheduler started (crawl + log purge).")

    yield

    scheduler.shutdown(wait=False)
    print("[AdyuBot] Shutting down…")


app = FastAPI(title="AdyuBot API", version="3.0.0", lifespan=lifespan)

# ── CORS ───────────────────────────────────────────────────────────────────────
origins = [FRONTEND_URL] if FRONTEND_URL != "*" else ["*"]
# Add common dev origins
if "http://localhost:5173" not in origins:
    origins.append("http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Admin Auth ─────────────────────────────────────────────────────────────────
async def verify_admin(x_admin_token: Optional[str] = Header(None)):
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

# ── Rate Limiter (thread-safe) ─────────────────────────────────────────────────
_rate_data: dict = defaultdict(lambda: {"count": 0, "window_start": time.time()})
_rate_lock = threading.Lock()
_rate_cleanup_counter = 0

def _maybe_clean_rate_limits():
    """Periodically remove stale IP buckets (every ~20 requests)."""
    global _rate_cleanup_counter
    _rate_cleanup_counter += 1
    if _rate_cleanup_counter % 20 == 0:
        now = time.time()
        stale = [ip for ip, b in list(_rate_data.items()) if now - b["window_start"] > RATE_WINDOW * 2]
        for ip in stale:
            del _rate_data[ip]

def check_rate_limit(ip: str) -> bool:
    with _rate_lock:
        _maybe_clean_rate_limits()
        now = time.time()
        bucket = _rate_data[ip]
        if now - bucket["window_start"] > RATE_WINDOW:
            bucket["count"] = 0
            bucket["window_start"] = now
        bucket["count"] += 1
        return bucket["count"] <= RATE_LIMIT

# ── LRU Cache with TTL (thread-safe) ──────────────────────────────────────────
_BAD_PHRASES = ("yeterli bilgi bulunamadı", "teknik bir hata", "yapılandırma hatası")

class SimpleCache:
    def __init__(self, capacity: int = CACHE_CAP):
        self.cache: OrderedDict = OrderedDict()
        self.capacity = capacity
        self._lock = threading.RLock()  # Reentrant lock for nested calls

    def get(self, key):
        with self._lock:
            if key not in self.cache:
                return None
            value, ts = self.cache[key]
            if time.time() - ts > CACHE_TTL:
                del self.cache[key]
                return None
            self.cache.move_to_end(key)
            return value

    def set(self, key, value):
        answer = value.get("answer", "")
        if any(p in answer for p in _BAD_PHRASES):
            return
        with self._lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = (value, time.time())
            if len(self.cache) > self.capacity:
                self.cache.popitem(last=False)

    def clear(self):
        with self._lock:
            self.cache.clear()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self.cache)

query_cache = SimpleCache()

# ── Cache metrics ──────────────────────────────────────────────────────────────
_cache_hits   = 0
_cache_misses = 0
_metrics_lock = threading.Lock()

# ── Request Model ──────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    question: str

# ── Endpoints ──────────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    uptime_s = int(time.time() - _startup_time)
    total_req = _cache_hits + _cache_misses
    hit_rate  = f"{(_cache_hits / total_req * 100):.1f}%" if total_req else "n/a"
    return {
        "status":         "ok",
        "version":        "3.0.0",
        "uptime_seconds": uptime_s,
        "cache_size":     query_cache.size,
        "cache_capacity": query_cache.capacity,
        "cache_hit_rate": hit_rate,
        "cache_hits":     _cache_hits,
        "cache_misses":   _cache_misses,
        "rate_limit":     f"{RATE_LIMIT} req/{RATE_WINDOW}s",
        "active_ips":     len(_rate_data),
    }

@app.post("/chat")
async def chat_endpoint(req: ChatRequest, request: Request):
    # ── Rate limiting ─────────────────────────────────────────────────────────
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Çok fazla istek gönderdiniz. Lütfen bir dakika bekleyin.",
        )

    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Soru boş olamaz.")
    if len(question) > MAX_QUESTION_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"Soru {MAX_QUESTION_LEN} karakterden uzun olamaz.",
        )

    # ── Forbidden topic guard ─────────────────────────────────────────────────
    if check_forbidden_topics(question):
        ans = "Bu asistan yalnızca Adıyaman Üniversitesi kapsamında hizmet vermektedir."
        await asyncio.to_thread(log_interaction, question, "", ans, "BLOCKED")
        return JSONResponse({"answer": ans, "sources": []})

    # ── Cache hit ────────────────────────────────────────────────────────────────
    cached = query_cache.get(question)
    if cached:
        with _metrics_lock:
            global _cache_hits
            _cache_hits += 1
        await asyncio.to_thread(
            log_interaction,
            question,
            ",".join(cached.get("sources", [])),
            cached["answer"],
            "CACHE_HIT",
        )
        return JSONResponse(cached)

    with _metrics_lock:
        global _cache_misses
        _cache_misses += 1

    # ── Live search (non-blocking) ────────────────────────────────────────────
    from live_search import get_live_context
    print(f"[/chat] Question: {question!r}")
    contexts, sources = await get_live_context(question)
    combined_context = "\n---\n".join(contexts)
    print(f"[/chat] Contexts: {len(contexts)}, chars: {len(combined_context)}")

    sources_list = sorted(sources)

    # ── Streaming response ────────────────────────────────────────────────────
    async def response_generator():
        full_answer = ""
        try:
            async for chunk in generate_answer_stream(question, combined_context):
                full_answer += chunk
                yield chunk
        except Exception as e:
            print(f"[/chat] Stream error: {e}")
            yield "Cevap üretilirken teknik bir hata oluştu."
            return

        # Append sources as a sentinel so the frontend can parse them
        if sources_list:
            yield "\n###SOURCES###" + "|".join(sources_list)

        # Cache & log after stream completes — non-blocking
        result = {"answer": full_answer, "sources": sources_list}
        await asyncio.to_thread(query_cache.set, question, result)
        await asyncio.to_thread(log_interaction, question, ",".join(sources_list), full_answer, "web")

    return StreamingResponse(response_generator(), media_type="text/plain; charset=utf-8")


# ── Admin endpoints ────────────────────────────────────────────────────────────
def _background_crawl():
    print("[Crawler] Starting background crawl…")
    try:
        chunks = scrape_site()
        vector_store.clear()
        vector_store.add_chunks(chunks)
        query_cache.clear()
        print(f"[Crawler] Done. {len(chunks)} chunks indexed.")
    except Exception as e:
        print(f"[Crawler] Failed: {e}")


@app.post("/admin/recrawl")
async def trigger_recrawl(background_tasks: BackgroundTasks, _=Depends(verify_admin)):
    background_tasks.add_task(_background_crawl)
    return {"message": "Recrawl başlatıldı (arka planda)."}


@app.get("/admin/logs")
async def fetch_logs(limit: int = 50, _=Depends(verify_admin)):
    return await asyncio.to_thread(get_recent_logs, limit)


@app.delete("/admin/cache")
async def clear_cache(_=Depends(verify_admin)):
    query_cache.clear()
    return {"message": "Cache temizlendi."}


@app.get("/admin/stats")
async def admin_stats(_=Depends(verify_admin)):
    total_req = _cache_hits + _cache_misses
    hit_rate  = f"{(_cache_hits / total_req * 100):.1f}%" if total_req else "n/a"
    uptime_s  = int(time.time() - _startup_time)
    return {
        "version":              "3.0.0",
        "uptime_seconds":       uptime_s,
        "cache_size":           query_cache.size,
        "cache_capacity":       query_cache.capacity,
        "cache_hits":           _cache_hits,
        "cache_misses":         _cache_misses,
        "cache_hit_rate":       hit_rate,
        "active_ips_tracked":   len(_rate_data),
        "rate_limit":           f"{RATE_LIMIT} req/{RATE_WINDOW}s",
    }
