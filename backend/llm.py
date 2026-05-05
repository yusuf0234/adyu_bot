"""
llm.py – LLM integration layer for AdyuBot v3.0
Optimizations over v2.4:
  - MAX_TOKENS_RESPONSE 1200 → 1500 (more complete answers)
  - FORBIDDEN_KEYWORDS expanded (more off-topic coverage)
  - Context trimmer word-boundary safe (unchanged)
  - Groq fallback to Gemini with retry (unchanged)
"""

import os
import time
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY   = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ── Client initialization ──────────────────────────────────────────────────────
groq_client = None
if GROQ_API_KEY:
    try:
        from groq import AsyncGroq
        groq_client = AsyncGroq(api_key=GROQ_API_KEY)
        print("[LLM] Groq client initialized.")
    except Exception as e:
        print(f"[LLM] WARNING: Groq init failed: {e}")

gemini_client = None
if GEMINI_API_KEY:
    try:
        from google import genai
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        print("[LLM] Gemini client initialized (fallback).")
    except Exception as e:
        print(f"[LLM] WARNING: Gemini init failed: {e}")

# ── Constants ──────────────────────────────────────────────────────────────────
GROQ_MODEL          = "llama-3.3-70b-versatile"
GEMINI_MODEL        = "gemini-2.0-flash"
MAX_QUESTION_LEN    = 500
MAX_CONTEXT_CHARS   = 12_000   # trim context to keep within token budget
MAX_TOKENS_RESPONSE = 1500     # increased from 1200 for more complete answers
TEMPERATURE         = 0.1

# ── Forbidden-topic filter ─────────────────────────────────────────────────────
FORBIDDEN_KEYWORDS = frozenset([
    # Politics
    "siyaset", "siyasi", "parti", "seçim", "cumhurbaşkanı", "iktidar", "muhalefet",
    "meclis", "milletvekili", "ak parti", "chp", "mhp", "hdp",
    # Sports scores (not university sports)
    "galatasaray", "fenerbahçe", "beşiktaş", "trabzonspor",
    "maç sonucu", "puan durumu", "şampiyon", "süper lig",
    # Finance
    "dolar kuru", "enflasyon", "euro kuru", "borsa", "altın fiyatı", "bitcoin",
    # Entertainment
    "film önerisi", "dizi önerisi", "netflix", "şarkı sözü", "muzik listesi",
    # Other off-topic
    "hava durumu", "tarif", "yemek tarifi", "günlük burcu", "burcu ne",
    "eş anlamlı", "kelime anlamı",
])

UNIVERSITY_CONTEXT_WORDS = frozenset([
    "adıyaman", "üniversite", "bölüm", "fakülte", "kampüs", "ders",
])


def check_forbidden_topics(question: str) -> bool:
    """
    Returns True when the question is clearly off-topic for a university chatbot.
    A single university-context word redeems an otherwise forbidden question.
    """
    q = question.lower()
    if any(ctx in q for ctx in UNIVERSITY_CONTEXT_WORDS):
        return False
    return any(word in q for word in FORBIDDEN_KEYWORDS)


# \u2500\u2500 Context trimmer (intelligent prioritization) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\r
def _trim_context(context: str, question: str = "") -> str:
    """
    Trim context to MAX_CONTEXT_CHARS. 
    If question is provided, prioritize blocks of text that contain keywords from the question.
    """
    if len(context) <= MAX_CONTEXT_CHARS:
        return context

    # Simple heuristic: Split into paragraphs/blocks and prioritize those with question keywords
    keywords = [w.lower() for w in question.split() if len(w) > 3]
    if not keywords:
        # Fallback to simple truncation if no good keywords
        cut = context[:MAX_CONTEXT_CHARS]
        last_space = cut.rfind(" ")
        return cut[:last_space] if last_space > MAX_CONTEXT_CHARS * 0.8 else cut

    blocks = context.split("\n\n")
    prioritized = []
    others = []
    
    current_len = 0
    for block in blocks:
        block_lower = block.lower()
        if any(kw in block_lower for kw in keywords):
            if current_len + len(block) < MAX_CONTEXT_CHARS:
                prioritized.append(block)
                current_len += len(block) + 2
        else:
            others.append(block)
            
    # Fill remaining space with other blocks
    for block in others:
        if current_len + len(block) < MAX_CONTEXT_CHARS:
            prioritized.append(block)
            current_len += len(block) + 2
        else:
            break
            
    return "\n\n".join(prioritized)


# ── System prompt (cached per calendar day) ────────────────────────────────────
_prompt_cache: dict[date, str] = {}

def _get_system_prompt() -> str:
    today = datetime.now().date()
    if today not in _prompt_cache:
        _prompt_cache.clear()  # discard yesterday's entry
        _prompt_cache[today] = (
            f"Sen Adıyaman Üniversitesi'nin resmi yapay zeka asistanısın. "
            f"Bugünün tarihi: {today.strftime('%d.%m.%Y')}\n\n"
            "GÖREVİN:\n"
            "1. Sunulan bağlam (context) bilgilerini analiz et ve kullanıcının sorusuna kapsamlı yanıt ver.\n"
            "2. Bağlamda '404', 'Hata', 'Sayfa Bulunamadı' gibi ifadeler varsa tamamen yoksay, yalnızca somut bilgilere odaklan.\n"
            "3. Bağlamda kesin yanıt yoksa ama ilgili bilgi varsa: 'Kesin bir bilgi bulamadım ancak web sitesinde şu bilgiler mevcut:' diyerek paylaş.\n"
            "4. Bağlamda HİÇBİR somut bilgi (tarih, birim, duyuru vb.) yoksa 'Bu konuda web sitesinde yeterli bilgi bulunamadı.' de.\n"
            "5. KESİNLİKLE bağlam dışı genel bilgi veya kendi bilgi birikimini kullanma.\n"
            "6. Selamlama sorularına asistan kimliğinle doğal ve kısa yanıt ver. 'Sen Adıyaman...' diye başlama.\n"
            "7. Yanıtlarını madde işaretleri ve başlıklar kullanarak düzenli sun.\n"
            "8. KESİNLİKLE SADECE Türkçe kullan. Asla Çince, Japonca veya İngilizce karıştırma.\n"
            "9. Yanıtında asla 'Bağlam:', 'Soru:' veya 'Cevap:' kelimelerini tekrar etme. Doğrudan yanıtla başla."
        )
    return _prompt_cache[today]


def _build_user_prompt(question: str, context: str) -> str:
    trimmed = _trim_context(context, question)
    ctx_block = trimmed if trimmed else "Bağlam bilgisi bulunamadı."
    return f"Bağlam:\n{ctx_block}\n\nSoru: {question}\n\nCevap:"


# ── Groq streaming with retry ──────────────────────────────────────────────────
import asyncio

async def _groq_stream(question: str, context: str, max_retries: int = 3):
    if not groq_client:
        raise RuntimeError("Groq client is not initialized.")

    delay = 2.0
    for attempt in range(max_retries + 1):
        try:
            stream = await groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": _get_system_prompt()},
                    {"role": "user",   "content": _build_user_prompt(question, context)},
                ],
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS_RESPONSE,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
            return  # success
        except Exception as e:
            err_str = str(e).lower()
            print(f"[LLM] Groq attempt {attempt} failed: {e}")
            is_rate_limit = any(code in err_str for code in ("429", "rate_limit"))
            is_retryable = is_rate_limit or any(code in err_str for code in ("503", "overloaded"))
            
            if is_retryable and attempt < max_retries:
                # ADAPTIVE TRUNCATION: If rate limited, reduce context drastically for the retry
                if is_rate_limit:
                    context = context[:len(context)//2]
                    print(f"[LLM] Groq rate limit hit. Retrying with half context.")
                
                await asyncio.sleep(delay)
                delay *= 2
                continue
            else:
                # Raise to allow fallback in generate_answer_stream
                raise e


# ── Gemini streaming with retry ────────────────────────────────────────────────
async def _gemini_stream(question: str, context: str, max_retries: int = 1):
    if not gemini_client:
        raise RuntimeError("Gemini client is not initialized.")
    from google.genai import types as gemini_types

    delay = 2.0
    for attempt in range(max_retries + 1):
        try:
            response = await gemini_client.aio.models.generate_content_stream(
                model=GEMINI_MODEL,
                contents=_build_user_prompt(question, context),
                config=gemini_types.GenerateContentConfig(
                    temperature=TEMPERATURE,
                    max_output_tokens=MAX_TOKENS_RESPONSE,
                    system_instruction=_get_system_prompt(),
                ),
            )
            async for chunk in response:
                if chunk.text:
                    yield chunk.text
            return  # success
        except Exception as e:
            err_str = str(e).lower()
            print(f"[LLM] Gemini attempt {attempt} failed: {e}")
            is_rate_limit = any(code in err_str for code in ("429", "rate_limit"))
            is_retryable = is_rate_limit or any(code in err_str for code in ("503", "overloaded"))
            
            if is_retryable and attempt < max_retries:
                # ADAPTIVE TRUNCATION: If rate limited, reduce context drastically for the retry
                if is_rate_limit:
                    context = context[:len(context)//2]
                    print(f"[LLM] Rate limit hit. Retrying with half context ({len(context)} chars).")
                
                await asyncio.sleep(delay)
                delay *= 2
                continue
            else:
                # Raise to allow fallback in generate_answer_stream
                raise e


# ── Public streaming API ───────────────────────────────────────────────────────
async def generate_answer_stream(question: str, context: str):
    """
    Generator that yields text chunks.
    Tries Groq first (with retry), then Gemini (with retry).
    """
    if not groq_client and not gemini_client:
        yield "Sistem şu anda yapılandırma hatası veriyor (API Key eksik)."
        return

    if check_forbidden_topics(question):
        yield "Bu asistan yalnızca Adıyaman Üniversitesi kapsamında hizmet vermektedir."
        return

    # Try Gemini first (better rate limits and context window)
    if gemini_client:
        try:
            async for chunk in _gemini_stream(question, context):
                yield chunk
            return
        except Exception as e:
            print(f"[LLM] Gemini failed, falling back to Groq: {e}")

    # Fallback to Groq
    if groq_client:
        try:
            async for chunk in _groq_stream(question, context):
                yield chunk
            return
        except Exception as e:
            print(f"[LLM] Groq failed: {e}")
            err_str = str(e).lower()
            if "429" in err_str or "rate" in err_str:
                yield "Sistem şu an çok yoğun (hız sınırı), lütfen birkaç saniye sonra tekrar deneyin."
            else:
                yield "Cevap üretilirken teknik bir hata ile karşılaşıldı. Lütfen tekrar deneyin."
            return

    yield "Cevap üretilirken teknik bir hata ile karşılaşıldı. Lütfen daha sonra tekrar deneyin."


async def generate_answer(question: str, context: str) -> str:
    """Non-streaming wrapper — mainly for tests."""
    chunks = []
    async for chunk in generate_answer_stream(question, context):
        chunks.append(chunk)
    return "".join(chunks)
