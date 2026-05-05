"""
live_search.py – Optimized live web search & scraping module for AdyuBot v3.0.
Key improvements:
  - Thread-safe TTL cache with max-size eviction
  - Word-boundary keyword matching (no false partial matches)
  - Smarter URL deduplication and ordering
  - Configurable timeouts and concurrency
  - Better encoding detection
  - Expanded CORE_FACTS (faculties, institutes, units)
  - Cleaner error handling and logging
"""

import re
import time
import threading
import asyncio

def safe_print(msg: str):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(str(msg).encode('ascii', 'backslashreplace').decode('ascii'))

import httpx
from bs4 import BeautifulSoup

# Try importing DDGS (package may be 'duckduckgo-search' or 'ddgs')
try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None
        safe_print("[live_search] WARNING: DuckDuckGo search library not found. Install 'ddgs' or 'duckduckgo-search'.")

# ── Config ─────────────────────────────────────────────────────────────────────
DEFAULT_TIMEOUT = 8        # seconds per HTTP request
MAX_CHUNK_LEN   = 5000     # max chars returned per scraped page
MAX_URLS        = 8        # max URLs to scrape per query
MAX_DDG_RESULTS = 5        # max DuckDuckGo results
MAX_WORKERS     = 6        # thread pool size for concurrent scraping
SCRAPE_TTL      = 3600     # 1 hour page cache
DDG_TTL         = 3600     # 1 hour search-result cache
FOOD_MENU_TTL   = 1800     # 30-minute cache for daily cafeteria menu
MAX_CACHE_SIZE  = 500      # max entries per cache (prevents unbounded growth)

# ── Word-boundary keyword helper ───────────────────────────────────────────────
def _has_kw(text: str, *keywords) -> bool:
    """Return True if any keyword appears as a whole word in text."""
    for kw in keywords:
        if re.search(r'(?<![\w\u00C0-\u024F])' + re.escape(kw) + r'(?![\w\u00C0-\u024F])', text):
            return True
    return False

# ── Thread-safe TTL Cache ──────────────────────────────────────────────────────
class TTLCache:
    """Thread-safe LRU-style cache with TTL and max-size eviction."""

    def __init__(self, ttl_seconds: int = 1800, max_size: int = MAX_CACHE_SIZE):
        self._cache: dict = {}
        self._lock = threading.Lock()
        self.ttl = ttl_seconds
        self.max_size = max_size

    def get(self, key):
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            val, ts = entry
            if time.time() - ts > self.ttl:
                del self._cache[key]
                return None
            return val

    def set(self, key, value):
        with self._lock:
            # Evict oldest entry if at capacity
            if len(self._cache) >= self.max_size and key not in self._cache:
                oldest = next(iter(self._cache))
                del self._cache[oldest]
            self._cache[key] = (value, time.time())

    def clear(self):
        with self._lock:
            self._cache.clear()


# ── Singleton caches ───────────────────────────────────────────────────────────
_scrape_cache = TTLCache(ttl_seconds=SCRAPE_TTL)
_ddg_cache    = TTLCache(ttl_seconds=DDG_TTL)

# ── Reusable HTTP session ──────────────────────────────────────────────────────
_HTTP_HEADERS = {
    'User-Agent':      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 AdyuBot/2.2',
    'Accept-Language': 'tr,en;q=0.9',
    'Accept':          'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
}

# ── Cafeteria-specific caches (short TTL — menu changes daily) ───────────────────
_food_cache = TTLCache(ttl_seconds=FOOD_MENU_TTL)

CAFETERIA_URL = "https://sksdb.adiyaman.edu.tr/tr/yemekhane/yemek-menusu"

# Turkish day names for display
_DAYS_TR = {
    0: "Pazartesi", 1: "Salı", 2: "Çarşamba",
    3: "Perşembe",  4: "Cuma",  5: "Cumartesi", 6: "Pazar",
}

async def scrape_cafeteria_menu(client: httpx.AsyncClient) -> str:
    """
    Fetches the cafeteria menu page and returns a formatted text block
    for today's date, including all meal options and calorie counts.
    Returns empty string on failure or when today's menu is unavailable.
    """
    from datetime import datetime
    today = datetime.now()
    today_str  = today.strftime("%d.%m.%Y")
    today_day  = _DAYS_TR.get(today.weekday(), "")

    cache_key = f"food_menu_{today_str}"
    cached = _food_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        r = await client.get(CAFETERIA_URL)
        r.raise_for_status()
        # Must use html.parser + explicit utf-8 decode to preserve Turkish chars.
        # lxml re-encodes incorrectly for this site's mixed-encoding pages.
        soup = BeautifulSoup(r.content.decode("utf-8", errors="replace"), "html.parser")

        items = soup.find_all("div", class_="item")
        for item in items:
            top_divs = item.find_all("div", recursive=False)
            if not top_divs:
                continue
            date_text = top_divs[0].get_text(strip=True)
            if today_str not in date_text:
                continue

            # Build menu blocks (each nested div group = one menu option)
            menu_blocks: list[str] = []
            for block_div in top_divs[1:]:
                sub_divs = block_div.find_all("div")
                lines = [s.get_text(strip=True) for s in sub_divs if s.get_text(strip=True)]
                if not lines:
                    continue

                # Last item that contains 'kcal' is the calorie count
                kcal = ""
                foods = []
                for ln in lines:
                    if "kcal" in ln.lower():
                        kcal = ln
                    else:
                        foods.append(ln)

                if foods:
                    block_text = ", ".join(foods)
                    if kcal:
                        block_text += f" ({kcal})"
                    menu_blocks.append(block_text)

            if menu_blocks:
                result = (
                    f"{today_str} {today_day} günü Adıyaman Üniversitesi yemekhane menüsü:\n"
                    + "\n".join(f"• {b}" for b in menu_blocks)
                )
            else:
                result = f"{today_str} tarihli yemek menüsü sayfada bulundu ancak içerik çıkarılamadı."

            _food_cache.set(cache_key, result)
            safe_print(f"[live_search] Cafeteria menu fetched for {today_str}: {len(menu_blocks)} menu(s)")
            return result

        # No item matched today's date
        result = f"{today_str} ({today_day}) tarihli yemek menüsü henüz yayınlanmamış olabilir."
        _food_cache.set(cache_key, result)
        return result

    except Exception as e:
        safe_print(f"[live_search] Cafeteria menu fetch failed: {e}")
        return ""


# ── Core University Facts (fast fallback, no network needed) ───────────────────
CORE_FACTS = [
    # (keyword_list, fact_text)
    (["rektör", "rektor"], "Adıyaman Üniversitesi Rektörü Prof. Dr. Mehmet Keleş'tir."),
    (["adres"], "Adıyaman Üniversitesi Adresi: Altınşehir Mah. 30001 Bulvar No:1 02040 ADIYAMAN."),
    (["iletişim", "telefon", "faks"], "Adıyaman Üniversitesi Telefon: +90 416 223 38 00 | Faks: +90 416 223 38 43"),
    (["kuruluş", "ne zaman kuruldu", "tarih"], "Adıyaman Üniversitesi 1 Mart 2006 tarihinde kurulmuştur."),
    (["kütüphane"], (
        "Adıyaman Üniversitesi Merkez Kütüphanesi: Hafta içi 08:00-17:00. "
        "Sınav dönemlerinde 24 saate çıkarılabilmektedir. Web: https://kutuphane.adiyaman.edu.tr/"
    )),
    (["fakülte", "fakülteler"], (
        "Adıyaman Üniversitesi Fakülteleri: Eğitim Fakültesi, Fen-Edebiyat Fakültesi, "
        "İktisadi ve İdari Bilimler Fakültesi, Mühendislik Fakültesi, Tıp Fakültesi, "
        "İlahiyat Fakültesi, Güzel Sanatlar Fakültesi, Beden Eğitimi ve Spor Yüksekokulu, "
        "Uygulamalı Bilimler Fakültesi, Diş Hekimliği Fakültesi."
    )),
    (["enstitü", "enstitüler"], (
        "Adıyaman Üniversitesi Enstitüleri: Fen Bilimleri Enstitüsü, "
        "Sosyal Bilimler Enstitüsü, Sağlık Bilimleri Enstitüsü."
    )),
    (["yüksekokul", "meslek yüksekokul", "myo"], (
        "Adıyaman Üniversitesi bünyesinde çeşitli Meslek Yüksekokulları bulunmaktadır: "
        "Adıyaman MYO, Besni MYO, Gölbaşı MYO, Kahta MYO, Samsat MYO ve diğerleri."
    )),
    (["öğrenci işleri", "oidb"], (
        "Öğrenci İşleri Daire Başkanlığı (OİDB): https://oidb.adiyaman.edu.tr/ "
        "Telefon: +90 416 223 38 00 (dahili)"
    )),
    (["bilgi işlem", "bidb"], "Bilgi İşlem Daire Başkanlığı: https://bidb.adiyaman.edu.tr/"),
    (["sağlık kültür spor", "sksdb", "sağlık merkezi"], (
        "Sağlık Kültür ve Spor Daire Başkanlığı: https://sksdb.adiyaman.edu.tr/ "
        "(Yemekhane, burs, yurt, sağlık hizmetleri)"
    )),
    (["kariyer", "kariyer merkezi", "staj merkezi"], (
        "Adıyaman Üniversitesi Kariyer ve Mezun İlişkileri Birimi staj ve kariyer rehberliği sunar. "
        "İletişim: https://www.adiyaman.edu.tr/"
    )),
    (["spor tesisi", "spor salonu", "spor kompleksi"], (
        "Adıyaman Üniversitesi kampüsünde spor tesisleri bulunmaktadır. "
        "Ayrıntı: https://sksdb.adiyaman.edu.tr/"
    )),
]

# ── Error-page keywords ────────────────────────────────────────────────────────
_ERROR_TITLE_KW  = {"sayfa bulunamadı", "404", "hata oluştu", "bulunamadı", "not found", "error"}
_ERROR_BODY_KW   = {"sayfa bulunamadı", "hata"}
_SKIP_TAGS       = {"script", "style", "nav", "footer", "header", "aside", "form", "noscript", "svg"}
_CONTENT_TAGS    = {"p", "h1", "h2", "h3", "h4", "li", "td", "th", "article", "section"}
_MIN_TEXT_LEN    = 20     # min chars for a tag to be kept
_MIN_STRUCTURED  = 200    # fallback to full-text if structured text shorter than this


async def scrape_url(url: str, client: httpx.AsyncClient) -> tuple[str, str]:
    """
    Fetch and clean text from *url*.
    Returns (url, text) — text is empty string on failure or error page.
    Uses a TTL cache to avoid redundant HTTP calls.
    """
    cached = _scrape_cache.get(url)
    if cached is not None:
        return url, cached

    try:
        r = await client.get(url)
        r.raise_for_status()

        # Encoding fix
        encoding = r.charset_encoding or 'windows-1254'
        if encoding.lower() in ('iso-8859-1', 'latin-1'):
            encoding = 'windows-1254'
        content_decoded = r.content.decode(encoding, errors="replace")

        try:
            soup = BeautifulSoup(content_decoded, 'lxml')
        except Exception:
            soup = BeautifulSoup(content_decoded, 'html.parser')

        # Skip error pages
        title_text = (soup.title.string or '').lower() if soup.title else ''
        if any(kw in title_text for kw in _ERROR_TITLE_KW):
            safe_print(f"[live_search] Skipping error page: {url} ({title_text[:60]})")
            _scrape_cache.set(url, '')
            return url, ''

        # Remove noise elements
        for tag in soup(_SKIP_TAGS):
            tag.decompose()

        # Collect content-rich text
        parts = [
            tag.get_text(separator=' ', strip=True)
            for tag in soup.find_all(_CONTENT_TAGS)
            if len(tag.get_text(strip=True)) > _MIN_TEXT_LEN
        ]
        structured = ' '.join(' '.join(parts).split())

        # Fallback to full page text if structured is too sparse
        if len(structured) < _MIN_STRUCTURED:
            structured = ' '.join(soup.get_text(separator=' ', strip=True).split())

        # Final error-phrase check
        if any(kw in structured[:120].lower() for kw in _ERROR_BODY_KW):
            _scrape_cache.set(url, '')
            return url, ''

        result = structured[:MAX_CHUNK_LEN]
        _scrape_cache.set(url, result)
        return url, result

    except httpx.TimeoutException:
        safe_print(f"[live_search] Timeout scraping {url}")
    except httpx.RequestError:
        safe_print(f"[live_search] Request error scraping {url}")
    except Exception as e:
        safe_print(f"[live_search] Failed to scrape {url}: {e}")

    _scrape_cache.set(url, '')
    return url, ''


async def _build_candidate_urls(question_lower: str) -> list[str]:
    """
    Build a prioritized, deduplicated list of URLs based on question keywords.
    Uses word-boundary matching to avoid false positives (e.g. 'kim' in 'akademik').
    High-priority (keyword-specific) URLs come first; DuckDuckGo results append last.
    """
    priority_urls: list[str] = []   # keyword-matched, high confidence
    ddg_urls:      list[str] = []   # from search engine
    q = question_lower

    # ── Cafeteria menu ─────────────────────────────────────────────────────────
    if _has_kw(q, "yemek", "menü", "menu", "yemekhane", "kafeterya", "bugün ne var", "öğle"):
        priority_urls.append("https://sksdb.adiyaman.edu.tr/tr/yemekhane/yemek-menusu")

    # ── Academic calendar / exams ──────────────────────────────────────────────
    if _has_kw(q, "akademik takvim", "takvim", "sınav takvimi", "vize", "final", "bütünleme", "dönem"):
        priority_urls.append("https://www.adiyaman.edu.tr/akademik-takvim")

    # ── Scholarships ──────────────────────────────────────────────────────────
    if _has_kw(q, "burs", "burs başvuru", "kredi", "burslar"):
        priority_urls += [
            "https://sksdb.adiyaman.edu.tr/tr/ogrenci-burs",
            "https://www.adiyaman.edu.tr/burs",
        ]

    # ── Dormitory / housing ────────────────────────────────────────────────────
    if _has_kw(q, "yurt", "yurtlar", "konut", "barınak", "kyk"):
        priority_urls += [
            "https://sksdb.adiyaman.edu.tr/tr/ogrenci-yurt",
            "https://www.adiyaman.edu.tr/yurt",
        ]

    # ── Erasmus / exchange ─────────────────────────────────────────────────────
    if _has_kw(q, "erasmus", "değişim", "mevlana", "farabi", "uluslararası"):
        priority_urls += [
            "https://www.adiyaman.edu.tr/uluslararasi-iliskiler",
            "https://erasmus.adiyaman.edu.tr/",
        ]

    # ── Internship ─────────────────────────────────────────────────────────────
    if _has_kw(q, "staj", "stajyer", "pratik eğitim"):
        priority_urls.append("https://www.adiyaman.edu.tr/staj")

    # ── Graduation / diploma ───────────────────────────────────────────────────
    if _has_kw(q, "mezuniyet", "diploma", "mezun"):
        priority_urls += [
            "https://oidb.adiyaman.edu.tr/tr/mezuniyet",
            "https://www.adiyaman.edu.tr/mezuniyet",
        ]

    # ── Rector / Management ────────────────────────────────────────────────────
    if _has_kw(q, "rektör", "rektor", "rektörlük", "rektorluk", "senato", "yönetim kurulu"):
        priority_urls += [
            "https://www.adiyaman.edu.tr/tr/rektor",
            "https://www.adiyaman.edu.tr/tr/yonetim/rektor",
            "https://www.adiyaman.edu.tr/tr/yonetim/rektor-yardimcilari",
            "https://www.adiyaman.edu.tr/tr/yonetim/genel-sekreter",
        ]

    # ── Registration / enrollment ──────────────────────────────────────────────
    if _has_kw(q, "kayıt", "kayıt yenileme", "ders kayıt", "ders seçimi", "ders ekleme"):
        priority_urls += [
            "https://oidb.adiyaman.edu.tr/",
            "https://www.adiyaman.edu.tr/kayit",
        ]

    # ── Health center ──────────────────────────────────────────────────────────
    if _has_kw(q, "sağlık merkezi", "sağlık birimi", "doktor", "revir"):
        priority_urls.append("https://sksdb.adiyaman.edu.tr/tr/saglik")

    # ── Sports facilities ──────────────────────────────────────────────────────
    if _has_kw(q, "spor", "spor salonu", "spor tesisi", "spor kompleksi"):
        priority_urls += [
            "https://sksdb.adiyaman.edu.tr/tr/spor",
            "https://besyo.adiyaman.edu.tr/",
        ]

    # ── Career / graduate ──────────────────────────────────────────────────────
    if _has_kw(q, "kariyer", "iş ilanı", "mezun takip"):
        priority_urls.append("https://www.adiyaman.edu.tr/kariyer")

    # ── Department / unit mappings ─────────────────────────────────────────────
    UNIT_MAP = {
        "bilgi işlem":    "bidb",
        "öğrenci işleri": "oidb",
        "personel daire": "personel",
        "kütüphane":      "kutuphane",
        "strateji":       "sgdb",
        "yapı işleri":    "yidb",
        "idari mali":     "imidb",
        "sağlık kültür":  "sksdb",
    }
    MANAGEMENT_KW = ["başkan", "yönetim", "müdür", "kadro"]

    for kw, sub in UNIT_MAP.items():
        if _has_kw(q, kw) or _has_kw(q, sub):
            base = f"https://{sub}.adiyaman.edu.tr/"
            priority_urls.append(base)
            if _has_kw(q, *MANAGEMENT_KW):
                priority_urls += [f"{base}tr/personel", f"{base}tr/yonetim"]

    # ── Academic staff / person queries (word-boundary 'kim' fix) ─────────────
    if _has_kw(q, "kimdir", "hoca", "prof", "doç", "öğretim üyesi", "araştırma görevlisi"):
        priority_urls += [
            "https://akademik.adiyaman.edu.tr/",
            "https://bidb.adiyaman.edu.tr/tr/personel",
            "https://www.adiyaman.edu.tr/tr/personel",
        ]
    # 'personel' ve 'başkan' ayrıca daha geniş ama word-boundary ile
    if _has_kw(q, "personel", "başkan") and not _has_kw(q, "kimdir", "hoca"):
        priority_urls += [
            "https://www.adiyaman.edu.tr/tr/personel",
            "https://akademik.adiyaman.edu.tr/",
        ]

    # ── DuckDuckGo search ──────────────────────────────────────────────────────
    if DDGS is not None:
        search_query = f"{question_lower} site:adiyaman.edu.tr"
        cached_hrefs = _ddg_cache.get(search_query)
        if cached_hrefs is not None:
            ddg_urls.extend(cached_hrefs)
        else:
            def sync_ddg():
                with DDGS() as ddgs:
                    results = list(ddgs.text(search_query, max_results=MAX_DDG_RESULTS))
                    if not results:
                        results = list(ddgs.text(f"Adıyaman Üniversitesi {question_lower}", max_results=3))
                    return [r.get('href', '') for r in results if r.get('href')]
            try:
                hrefs = await asyncio.to_thread(sync_ddg)
                _ddg_cache.set(search_query, hrefs)
                ddg_urls.extend(hrefs)
            except Exception as e:
                safe_print(f"[live_search] DuckDuckGo search error: {e}")
    else:
        safe_print("[live_search] Skipping DuckDuckGo search — library not available.")

    # ── Deduplicate preserving priority order ──────────────────────────────────
    seen: set[str] = set()
    unique: list[str] = []
    for url in priority_urls + ddg_urls:
        if url and url not in seen:
            seen.add(url)
            unique.append(url)

    return unique[:MAX_URLS]


_FOOD_KEYWORDS = frozenset(["yemek", "menü", "menu", "yemekhane", "kafeterya", "bugün ne var", "öğle yemeği"])

async def get_live_context(question: str) -> tuple[list[str], set[str]]:
    """
    Main entry point called by main.py.
    Returns (contexts_list, sources_set).

    For food/cafeteria queries, calls the dedicated scrape_cafeteria_menu()
    which correctly parses today's date from the structured div layout and
    injects it as the FIRST context (highest LLM priority).
    """
    question_lower = question.lower()

    # ── Dedicated cafeteria menu (structured parser, highest priority) ─────────
    is_food_query = any(kw in question_lower for kw in _FOOD_KEYWORDS)
    pre_contexts: list[str] = []
    pre_sources:  set[str]  = set()

    async with httpx.AsyncClient(timeout=httpx.Timeout(DEFAULT_TIMEOUT), headers=_HTTP_HEADERS, follow_redirects=True) as client:
        if is_food_query:
            menu_text = await scrape_cafeteria_menu(client)
            if menu_text:
                pre_contexts.append(menu_text)
                pre_sources.add(CAFETERIA_URL)

        # ── Core facts (no network, always fast) ──────────────────────────────────
        for keywords, fact in CORE_FACTS:
            if _has_kw(question_lower, *keywords):
                pre_contexts.append(fact)
                pre_sources.add("Sistem Bilgisi")

        urls = await _build_candidate_urls(question_lower)

        # For pure food queries, skip generic URL scraping if we already have menu data
        if is_food_query and pre_contexts:
            # Still scrape the cafeteria URL for supplementary context (dish details etc.)
            # but skip unrelated pages
            urls = [u for u in urls if "sksdb" in u or "yemek" in u]

        if not urls:
            return pre_contexts, pre_sources

        # ── Concurrent scraping ────────────────────────────────────────────────────
        url_to_text: dict[str, str] = {}
        
        tasks = [scrape_url(url, client) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for url, res in zip(urls, results):
            if isinstance(res, Exception):
                safe_print(f"[live_search] Async task error for {url}: {res}")
            else:
                fetched_url, text = res
                if text and text.strip():
                    url_to_text[fetched_url] = text

    # ── Build results preserving original URL order ────────────────────────────
    contexts: list[str] = list(pre_contexts)
    sources:  set[str]  = set(pre_sources)
    for url in urls:
        if url in url_to_text:
            contexts.append(url_to_text[url])
            sources.add(url)

    return contexts, sources
