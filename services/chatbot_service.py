"""
TripWise Smart Chatbot Service — Zero Paid API, Full Intelligence.

Architecture:
  1. INTENT ROUTER  — decides which services to call before answering.
  2. DATA FETCHER   — calls weather, currency, search, budget, transport services as needed.
  3. AI RESPONSE    — passes enriched context to Gemini (free tier) or local Ollama when available.
  4. OFFLINE ENGINE — context-aware expert fallback when external AI is unavailable.

Free services used:
  - Google Gemini 1.5 Flash (free quota) via REST
  - Ollama local LLM (optional, runs locally)
  - DuckDuckGo via duckduckgo_search / ddgs (no API key)
  - Open-Meteo weather (no API key)
  - Frankfurter.app currency rates (no API key, European Central Bank data)
"""

from __future__ import annotations
import math
import os
import re
import time
import logging
import requests
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ─── API Keys & Local Model Settings (optional — all features work without them) ─
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "").strip()
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "mistral:7b").strip()

# Cache unavailable status for external backends to avoid slow repeated failures
_OLLAMA_UNAVAILABLE_UNTIL: float = 0.0
_OLLAMA_CHECK_INTERVAL: float = 60.0  # seconds

_GEMINI_UNAVAILABLE_UNTIL: float = 0.0
_GEMINI_CHECK_INTERVAL: float = 60.0  # seconds


# ─── Destination seasonal knowledge ─────────────────────────────────────────
DESTINATION_BEST_TIME = {
    "goa": {
        "peak": "October to March",
        "avoid": "June to September (monsoon — heavy rain, beaches closed)",
        "best_months": "November, December, January",
        "festivals": "Sunburn Festival (Dec), Carnival (Feb/Mar), Shigmo Festival (Mar)",
        "notes": "Winter is perfect for beaches, water sports, and nightlife. Shoulder season (Oct, Mar) has fewer crowds. Monsoon offers lush greenery but most beach shacks close."
    },
    "visakhapatnam": {
        "peak": "October to March",
        "avoid": "May to July (peak summer and pre-monsoon, very hot)",
        "best_months": "November, December, January, February",
        "festivals": "Vizag Utsav (Nov), Beach Festival (Dec)",
        "notes": "Winter months are ideal for beaches and sightseeing. The city experiences cyclonic weather October–November — check forecasts."
    },
    "hyderabad": {
        "peak": "October to February",
        "avoid": "March to June (hot and dry, up to 42°C)",
        "best_months": "October, November, December, January, February",
        "festivals": "Bathukamma (Oct), Bonalu (Jul/Aug), Deccan Festival",
        "notes": "Post-monsoon winter is the most comfortable period for sightseeing, heritage walks, and food tours."
    },
    "paris": {
        "peak": "June to August (summer) and December (Christmas)",
        "avoid": "July and August if you dislike crowds and queues",
        "best_months": "April, May, September, October",
        "festivals": "Bastille Day (14 Jul), Paris Fashion Week (Sep/Oct), Noel Christmas Markets (Dec)",
        "notes": "Spring and autumn offer mild weather with fewer tourists. Summer is vibrant but crowded. Winter is magical for Christmas markets."
    },
    "tokyo": {
        "peak": "March–April (cherry blossom) and October–November (autumn foliage)",
        "avoid": "July–August (humid and very hot)",
        "best_months": "March, April, October, November",
        "festivals": "Hanami (cherry blossom, Mar–Apr), Obon Festival (Aug), Shichi-Go-San (Nov)",
        "notes": "Spring cherry blossoms are spectacular but hotels book months in advance. Autumn colours are equally beautiful with smaller crowds."
    },
    "bali": {
        "peak": "July to August (dry season peak)",
        "avoid": "November to March (wet season — heavy daily rains)",
        "best_months": "April, May, June, September, October",
        "festivals": "Nyepi (Balinese New Year, Mar), Galungan Festival (every 210 days)",
        "notes": "Shoulder season (Apr–Jun, Sep–Oct) offers great weather with fewer tourists and lower prices."
    },
    "mumbai": {
        "peak": "November to February",
        "avoid": "June to September (heavy monsoon rains)",
        "best_months": "November, December, January, February",
        "festivals": "Ganesh Chaturthi (Aug/Sep), Diwali (Oct/Nov), Kala Ghoda Arts Festival (Feb)",
        "notes": "Winter is mild and perfect for exploring the city. Monsoon rains are heavy but the city's street food scene thrives."
    },
    "jaipur": {
        "peak": "October to March",
        "avoid": "April to June (extreme heat, up to 45°C)",
        "best_months": "November, December, January, February",
        "festivals": "Jaipur Literature Festival (Jan), Teej (Jul/Aug), Diwali (Oct/Nov)",
        "notes": "Winter is ideal for heritage walks, palace tours, and outdoor activities. The pink city is most photogenic in clear winter light."
    },
    "kerala": {
        "peak": "October to March (post-monsoon)",
        "avoid": "June to September (heavy monsoon — backwaters flood)",
        "best_months": "November, December, January, February",
        "festivals": "Onam (Aug/Sep), Thrissur Pooram (Apr/May), Vishu (Apr)",
        "notes": "Winter is perfect for houseboat cruises, Ayurveda retreats, and wildlife safaris. Monsoon (Karippatt) is a unique experience but trails may close."
    },
    "thailand": {
        "peak": "November to February (cool & dry season)",
        "avoid": "July to October (monsoon season with heavy tropical downpours)",
        "best_months": "November, December, January, February",
        "festivals": "Songkran Water Festival (Apr), Loy Krathong Lantern Festival (Nov)",
        "notes": "Winter brings ideal 28–32°C weather for Bangkok temples, Chiang Mai culture, and Phuket/Krabi beaches. March–May is hot, and July–October sees monsoon rains."
    },
    "bangkok": {
        "peak": "November to February",
        "avoid": "September to October (peak rainfall and localized canal flooding)",
        "best_months": "November, December, January, February",
        "festivals": "Songkran (Apr), Loy Krathong (Nov), Chinese New Year (Jan/Feb)",
        "notes": "Winter is comfortable for sightseeing. Use the BTS Skytrain and MRT to avoid heavy Bangkok road traffic."
    }
}

DESTINATION_TIPS = {
    "thailand": [
        "Dress respectfully for temples: shoulders and knees must be covered, remove shoes at entrances.",
        "Take metered taxis or use Grab instead of unmetered tuk-tuks to avoid overcharging.",
        "Eat where locals queue — Thai street food and night markets are cheap, delicious, and safe.",
        "Download Grab and Google Translate (Thai camera translation is very handy).",
        "Keep 100–500 THB in small notes for street vendors, boats, and markets.",
        "Stay hydrated and carry sunscreen SPF 50+ — tropical sun is strong even on overcast days."
    ],
    "goa": [
        "Rent a scooter (₹300–400/day) — the most flexible way to get around.",
        "Carry cash — many beach shacks and vendors don't accept cards.",
        "Book water sports (parasailing, jet-ski) early morning to avoid peak crowds.",
        "Avoid peak hours at Baga and Calangute — visit at sunrise or late evening.",
        "Many beach shacks are seasonal — check in advance if visiting in October or April.",
        "Dudhsagar Waterfalls trip requires jeep safari booking — plan 1–2 days ahead.",
        "Haggling is acceptable at Anjuna Flea Market and Mapusa market."
    ],
    "visakhapatnam": [
        "RK Beach is the central hub — start your Vizag exploration here.",
        "Hire an auto-rickshaw for city sightseeing (₹100–200 for short trips).",
        "Borra Caves and Araku Valley can be combined into a single day trip.",
        "INS Kursura Submarine Museum closes on Mondays — check timing before visiting.",
        "Fresh seafood is excellent at RK Beach shacks — try the prawns and fish fry.",
        "Simhachalam Temple gets very crowded on weekends — visit on weekdays.",
        "Kailasagiri has scenic harbour views — visit at sunset."
    ],
    "hyderabad": [
        "Book Ramoji Film City tickets online in advance — it gets crowded on weekends.",
        "The Old City area (Charminar, Laad Bazaar) is best explored on foot or by auto.",
        "Hyderabadi Biryani at Paradise or Bawarchi is an essential culinary experience.",
        "Salar Jung Museum is massive — allocate at least 3 hours and start early.",
        "Golconda Fort has a spectacular sound-and-light show in the evenings.",
        "Chowmahalla Palace closes on Fridays — plan accordingly.",
        "Hyderabad traffic is heavy — plan 30–45 extra minutes between attractions."
    ],
    "paris": [
        "Book Eiffel Tower summit tickets well in advance — often sold out 1–2 months ahead.",
        "The Paris Museum Pass (2, 4, or 6 days) covers 50+ museums and saves money.",
        "Metro is the fastest way to get around — buy a Navigo weekly or carnet of 10 tickets.",
        "Many major museums are free on the first Sunday of each month.",
        "Restaurants typically serve lunch 12:00–14:30 and dinner 19:30–22:30.",
        "Pickpocketing is common at tourist hotspots — keep valuables in front pockets.",
        "Versailles is a full-day trip — go early to avoid the longest queues."
    ],
    "mumbai": [
        "Local trains are the fastest way to get around — buy a day pass.",
        "Street food at Juhu Beach, Mohammed Ali Road, and Chowpatty Beach is excellent.",
        "The Gateway of India is best visited early morning or evening to avoid crowds.",
        "Marine Drive (Queen's Necklace) is magical after sunset — visit on foot.",
        "Traffic in Mumbai can be extreme — allocate double the expected travel time."
    ]
}


# ─── Free Currency Rate Source ───────────────────────────────────────────────
_CURRENCY_CACHE: dict = {}
_CURRENCY_CACHE_TS: float = 0.0
_CURRENCY_CACHE_TTL = 3600  # 1 hour


def _get_free_exchange_rates() -> dict:
    """Fetch exchange rates from Frankfurter API (free, no key required, ECB data)."""
    global _CURRENCY_CACHE, _CURRENCY_CACHE_TS
    if _CURRENCY_CACHE and (time.time() - _CURRENCY_CACHE_TS) < _CURRENCY_CACHE_TTL:
        return _CURRENCY_CACHE
    try:
        resp = requests.get(
            "https://api.frankfurter.app/latest?base=INR",
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            rates = data.get("rates", {})
            rates["INR"] = 1.0
            updated = data.get("date", "unknown")
            _CURRENCY_CACHE = {
                "rates": rates,
                "updated": updated,
                "source": "Frankfurter.app (European Central Bank)"
            }
            _CURRENCY_CACHE_TS = time.time()
            return _CURRENCY_CACHE
    except Exception as exc:
        logger.warning("Currency fetch failed: %s", exc)
    # Static fallback rates
    return {
        "rates": {
            "INR": 1.0, "USD": 0.012, "EUR": 0.011, "GBP": 0.0094,
            "SGD": 0.016, "AED": 0.044, "THB": 0.41, "JPY": 1.78
        },
        "updated": "static-fallback",
        "source": "Offline estimated rates (Frankfurter.app unavailable)"
    }


# ─── Ollama Configuration & Health Check (Phase 2) ──────────────────────────

def _get_ollama_config() -> tuple[str | None, str | None]:
    """
    Returns normalized (base_url, model) or (None, None) if not configured or invalid.
    Normalizes empty environment variables and validates URL scheme and hostname.
    """
    raw_url = os.getenv("OLLAMA_BASE_URL", "").strip() or OLLAMA_BASE_URL
    if not raw_url:
        return None, None

    if not re.match(r"^https?://", raw_url, re.IGNORECASE):
        raw_url = f"http://{raw_url}"

    clean_url = raw_url.rstrip("/")
    try:
        parsed = urlparse(clean_url)
        if not parsed.scheme or not parsed.netloc:
            return None, None
    except Exception:
        return None, None

    model = os.getenv("OLLAMA_MODEL", "").strip() or OLLAMA_MODEL or "mistral:7b"
    return clean_url, model


def _is_ollama_available(base_url: str) -> bool:
    """Checks if Ollama server is reachable, caching failure for 60s."""
    global _OLLAMA_UNAVAILABLE_UNTIL
    now = time.time()
    if now < _OLLAMA_UNAVAILABLE_UNTIL:
        return False
    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=1.0)
        if resp.status_code == 200:
            return True
        _OLLAMA_UNAVAILABLE_UNTIL = now + _OLLAMA_CHECK_INTERVAL
        return False
    except Exception:
        _OLLAMA_UNAVAILABLE_UNTIL = now + _OLLAMA_CHECK_INTERVAL
        return False


def _call_ollama(system_prompt: str, user_message: str, history: list[dict]) -> str | None:
    """Call a local Ollama LLM. Returns text or None if Ollama is unconfigured, unreachable, or fails."""
    base_url, model = _get_ollama_config()
    if not base_url or not model:
        return None

    if not _is_ollama_available(base_url):
        return None

    try:
        messages = [{"role": "system", "content": system_prompt}]
        for h in history[-8:]:
            role = "user" if h.get("sender") == "user" else "assistant"
            messages.append({"role": role, "content": str(h.get("text", ""))[:500]})
        messages.append({"role": "user", "content": user_message})

        endpoint = f"{base_url}/api/chat"
        resp = requests.post(
            endpoint,
            json={"model": model, "messages": messages, "stream": False},
            timeout=15
        )
        if resp.status_code == 200:
            data = resp.json()
            content = data.get("message", {}).get("content", "").strip()
            if content:
                return content
        logger.warning("Ollama returned HTTP %s", resp.status_code)
        return None
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
        logger.info("Ollama unreachable or timed out: %s", exc)
        return None
    except Exception as exc:
        logger.warning("Ollama call failed: %s", exc)
        return None


# ─── Gemini Configuration & Execution (Phase 4) ──────────────────────────────

def _call_gemini(system_prompt: str, user_message: str, history: list[dict]) -> str | None:
    """Call Gemini 1.5 Flash (free tier). Returns text or None on failure."""
    global _GEMINI_UNAVAILABLE_UNTIL
    now = time.time()
    if now < _GEMINI_UNAVAILABLE_UNTIL:
        return None

    key = os.getenv("GEMINI_API_KEY", "").strip() or GEMINI_API_KEY
    if not key:
        return None

    model = os.getenv("GEMINI_MODEL", "").strip() or GEMINI_MODEL or "gemini-2.5-flash"
    try:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={key}"
        )
        contents = []
        for h in history[-10:]:
            role = "user" if h.get("sender") == "user" else "model"
            contents.append({"role": role, "parts": [{"text": str(h.get("text", ""))[:800]}]})
        contents.append({"role": "user", "parts": [{"text": user_message}]})

        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": contents,
            "generation_config": {"temperature": 0.7, "max_output_tokens": 1000}
        }
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
        elif resp.status_code == 429:
            logger.warning("Gemini quota exhausted (429). Caching unavailable status.")
            _GEMINI_UNAVAILABLE_UNTIL = now + _GEMINI_CHECK_INTERVAL
        elif resp.status_code in (400, 401, 403):
            logger.warning("Gemini API key rejected (%s). Caching unavailable status.", resp.status_code)
            _GEMINI_UNAVAILABLE_UNTIL = now + _GEMINI_CHECK_INTERVAL
        else:
            logger.warning("Gemini returned %s: %s", resp.status_code, resp.text[:200])
        return None
    except Exception as exc:
        logger.warning("Gemini API call failed: %s", exc)
        return None


def _call_openai(system_prompt: str, user_message: str, history: list[dict], api_key: str) -> str | None:
    """Optional OpenAI GPT-4o-mini if user explicitly provided a key."""
    try:
        messages = [{"role": "system", "content": system_prompt}]
        for h in history[-8:]:
            messages.append({
                "role": "user" if h.get("sender") == "user" else "assistant",
                "content": str(h.get("text", ""))[:600]
            })
        messages.append({"role": "user", "content": user_message})
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "gpt-4o-mini", "messages": messages, "max_tokens": 1000, "temperature": 0.7},
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
        logger.warning("OpenAI returned %s: %s", resp.status_code, resp.text[:200])
        return None
    except Exception as exc:
        logger.warning("OpenAI call failed: %s", exc)
        return None


# ─── Intent Router (Phase 5 & 6) ────────────────────────────────────────────

class Intent:
    GREETING      = "greeting"
    DEST_CHANGE   = "destination_change"   # NEW: user is changing to a different destination
    MODIFY        = "modify_itinerary"
    DAY_RECALL    = "day_recall"
    WEATHER       = "weather"
    BUDGET        = "budget"
    TRANSPORT     = "transport"
    ATTRACTIONS   = "attractions"
    NEARBY        = "nearby"
    DISTANCE      = "distance"
    FOOD          = "food"
    PACKING       = "packing"
    SAFETY        = "safety"
    BEST_TIME     = "best_time"
    CURRENCY      = "currency"
    TIPS          = "tips"
    SEARCH        = "web_search"
    GENERAL       = "general"


# ─── Destination Entity Extraction ───────────────────────────────────────────

KNOWN_DESTINATIONS = [
    "goa", "visakhapatnam", "vizag", "hyderabad", "mumbai", "delhi", "jaipur",
    "kerala", "bali", "paris", "tokyo", "bangkok", "singapore", "dubai",
    "thailand", "japan", "maldives", "switzerland", "london", "new york",
    "rome", "amsterdam", "toronto", "sydney", "bhubaneswar", "kolkata",
    "chennai", "bangalore", "bengaluru", "manali", "shimla", "darjeeling",
    "ooty", "munnar", "rishikesh", "varanasi", "agra", "rajasthan",
    "phuket", "hong kong", "seoul", "kuala lumpur", "istanbul",
]

# Phrases that signal the user wants to switch destination
_DEST_CHANGE_PHRASES = [
    r"(?:actually[,\s]+)?(?:i want|i'd like|prefer)\s+(?:to visit |to go to |to plan for )?(\w[\w\s]+?)(?:\s+instead|\s*$|\?)",
    r"(\w[\w\s]+?)\s+instead",
    r"(?:actually|ok|okay|wait|no)[,\s]+(?:let(?:'s)?|i want to|i want)\s+(?:go|plan|visit)?\s*(?:to\s+)?(\w[\w\s]+?)(?:\s*$|\?)",
    r"i want to (?:visit|go to|travel to|plan for|see)\s+(?:to\s+)?(\w[\w\s]+?)(?:\s+instead|\s*$|\?)",
    r"(?:change|switch|update)\s+(?:to|destination to|it to)\s+(\w[\w\s]+?)(?:\s+instead|\s*$|\?)",
    r"(?:forget|cancel|never mind)\s+\w+[,\s]+(?:plan|go|visit)\s+(?:to\s+)?(\w[\w\s]+?)(?:\s*$|\?)",
    r"(?:what about|how about)\s+(\w[\w\s]+?)(?:\s+instead|\s+trip|\s*$|\?)",
    r"plan (?:a )?trip to\s+(\w[\w\s]+?)(?:\s*$|\?)",
    r"(?:let(?:'s)?)\s+(?:go to|plan for|visit)\s+(\w[\w\s]+?)(?:\s*$|\?)",
]


def extract_destination_entity(text: str) -> tuple[str | None, bool]:
    """
    Attempts to find a known destination in ``text`` that the user wants to
    *switch to* (not just mention as part of a question about the current trip).

    Returns:
        (destination_name_title_case, is_explicit_change)
        – ``is_explicit_change`` is True when the user clearly expressed
          a *switch* (phrases like "I want to visit X instead").
        – Returns (None, False) when nothing is found, or when the destination
          is merely referenced in a question about the current destination.
    """
    q = text.strip().lower().rstrip(".,!?")

    # --- Do NOT flag as a change if the message contains these verbs that imply
    #     the user is asking ABOUT their current destination, not switching.
    # e.g. "What food should I try in Goa?" / "tips for visiting Goa" / "best time in Goa"
    is_question_about_dest = (
        text.strip().endswith("?") or
        re.search(r"\b(what|when|how|where|which|give|show|tell|suggest|tips|best|top|food|weather|pack|visit|try)\b", q) is not None
    )

    # 1. Explicit change phrases (highest confidence)
    for pattern in _DEST_CHANGE_PHRASES:
        m = re.search(pattern, q)
        if m:
            candidate = m.group(1).strip().rstrip(".,!?")
            for dest in KNOWN_DESTINATIONS:
                if dest in candidate or candidate in dest:
                    return (dest.title(), True)

    # 2. Bare destination name — the WHOLE message is JUST a destination
    #    (and it's not a question asking about the current destination)
    stripped = q.strip().rstrip("!?.,")
    for dest in KNOWN_DESTINATIONS:
        if stripped == dest or stripped == dest.replace("_", " "):
            return (dest.title(), True)

    # 3. Very short message (≤3 words) containing a destination and NO question words
    words = q.split()
    if len(words) <= 3 and not is_question_about_dest:
        for dest in KNOWN_DESTINATIONS:
            dest_words = dest.split()
            if all(dw in words for dw in dest_words):
                return (dest.title(), True)

    return (None, False)


def update_context_for_destination_change(ctx: dict, new_dest: str) -> dict:
    """
    Returns a *new* context dict with the destination set to ``new_dest``
    and all destination-specific cached data cleared.
    Preserves travel-agnostic fields like start_location, travelers, currency.
    """
    preserved_keys = {
        "start_location", "travelers", "currency", "num_days",
        "start_date", "end_date", "budget_per_person",
    }
    new_ctx: dict = {k: v for k, v in ctx.items() if k in preserved_keys}
    new_ctx["destination"] = new_dest
    return new_ctx


def classify_intent(message: str, history: list[dict]) -> list[str]:
    """
    Returns an ordered list of intents for the message.
    Destination-change intent takes absolute priority; modification before day-recall.
    """
    q = message.lower()
    intents = []

    # 0. Destination change (highest priority — check before anything else)
    new_dest, is_change = extract_destination_entity(message)
    current_dest = ""
    for h in reversed(history[-6:]):
        m = re.search(r"\b(goa|visakhapatnam|hyderabad|mumbai|delhi|jaipur|kerala|bali|paris|tokyo|bangkok|singapore|dubai|thailand|japan)\b", h.get("text", "").lower())
        if m:
            current_dest = m.group(1)
            break
    if new_dest and is_change and new_dest.lower() != current_dest:
        intents.append(Intent.DEST_CHANGE)

    # 1. Greetings (match standalone greetings, not embedded in longer questions)
    q_stripped = q.strip()
    is_greeting = (
        q_stripped in {"hi", "hii", "hiii", "hey", "hello", "yo", "namaste", "hola", "greetings", "hi!", "hello!", "hey!"}
        or q_stripped.startswith(("hi ", "hey ", "hello ", "good morning", "good evening", "good afternoon", "good night"))
        or any(q_stripped == k for k in ["hi there", "hey there", "hello there"])
    )
    if is_greeting:
        intents.append(Intent.GREETING)

    # 2. Itinerary modification check FIRST so "replace day 2 activity" isn't misrouted to day recall
    is_modify = any(k in q for k in [
        "replace", "change", "swap", "substitute", "instead of",
        "alternative", "another option", "different option", "what else can i visit",
        "what else should i see", "modify", "switch"
    ])
    if is_modify:
        intents.append(Intent.MODIFY)

    # 3. Day recall (only when user is not requesting a replacement/modification)
    if not is_modify:
        if re.search(r"\bday\s*\d+\b", q) or any(w in q for w in ["first day", "second day", "third day", "fourth day", "day one", "day two", "day three", "day four"]):
            intents.append(Intent.DAY_RECALL)

    # 4. Weather
    if any(k in q for k in ["weather", "temperature", "forecast", "climate", "rain", "hot", "cold", "humidity", "wind", "sunny", "snow"]):
        intents.append(Intent.WEATHER)
        if any(k in q for k in ["current", "today", "now", "this week", "2024", "2025", "2026"]):
            intents.append(Intent.SEARCH)

    # 5. Budget / cost
    if any(k in q for k in ["budget", "cost", "how much", "price", "cheaper", "save money", "shortfall", "expensive", "reduce", "afford", "money", "rupee", "₹", "dollar", "euro"]):
        intents.append(Intent.BUDGET)

    # 6. Transport
    if any(k in q for k in ["transport", "how to get", "how do i get", "getting there", "travel from", "reach", "flight", "train", "bus", "taxi", "cab", "drive", "car", "auto", "metro", "ferry"]):
        intents.append(Intent.TRANSPORT)

    # 7. Attractions
    if any(k in q for k in ["places to visit", "suggest places", "what to visit", "top places", "attractions", "sightseeing", "must see", "must visit", "what to see", "tourist spots", "landmarks", "things to do"]) or re.search(r"\b(?:what\s+places|places\s+(?:to\s+visit|should\s+i\s+visit|can\s+i\s+visit)|what\s+to\s+visit|what\s+to\s+see|places\s+to\s+see)\b", q):
        intents.append(Intent.ATTRACTIONS)

    # 8. Nearby
    if any(k in q for k in ["near", "closest to", "around", "nearby", "close to"]):
        intents.append(Intent.NEARBY)

    # 9. Distance
    if re.search(r"distance\s+between|how\s+far\s+is", q):
        intents.append(Intent.DISTANCE)

    # 10. Food
    if any(k in q for k in ["food", "dish", "cuisine", "eat", "restaurant", "taste", "dining", "lunch", "dinner", "breakfast", "snack", "drink", "street food", "must eat", "best food"]):
        intents.append(Intent.FOOD)
        if any(k in q for k in ["best restaurant", "must eat", "top restaurant", "where to eat"]):
            intents.append(Intent.SEARCH)

    # 11. Packing
    if any(k in q for k in ["pack", "luggage", "wear", "clothes", "what to bring", "carry", "bag", "suitcase", "wardrobe"]):
        intents.append(Intent.PACKING)

    # 12. Safety / visa
    if any(k in q for k in ["visa", "passport", "entry", "safe", "safety", "dangerous", "crime", "emergency", "require"]):
        intents.append(Intent.SAFETY)
        intents.append(Intent.SEARCH)

    # 13. Best time to visit
    if any(k in q for k in ["best time", "best season", "when to visit", "when should i", "what month", "good time", "ideal time", "right time", "which month"]):
        intents.append(Intent.BEST_TIME)

    # 14. Currency
    if any(k in q for k in ["currency", "exchange rate", "convert", "dollar", "euro", "pound", "usd", "eur", "gbp", "how much is"]):
        intents.append(Intent.CURRENCY)

    # 15. Tips
    if any(k in q for k in ["tips", "advice", "tricks", "suggest", "recommendation", "guide", "must know", "insider"]):
        intents.append(Intent.TIPS)

    # 16. Web search triggers
    if any(k in q for k in ["open hours", "opening hours", "entry fee", "ticket price", "is it open", "when does", "current price", "2024", "2025", "2026", "news", "festival", "event"]):
        intents.append(Intent.SEARCH)

    # Deduplicate preserving order
    seen: set = set()
    unique = []
    for i in intents:
        if i not in seen:
            seen.add(i)
            unique.append(i)

    return unique if unique else [Intent.GENERAL]


def _resolve_context_from_history(message: str, history: list[dict], ctx: dict) -> dict:
    """
    Extracts implicit context from conversation history AND current message.
    Handles destination changes, traveler count updates, budget updates,
    and resolves destination pronouns ('there', 'it').
    """
    resolved = dict(ctx)
    q = message.lower()

    # ── Destination change: current message signals a new destination ──
    new_dest, is_change = extract_destination_entity(message)
    if new_dest and is_change:
        old_dest = resolved.get("destination", "")
        if old_dest.lower() != new_dest.lower():
            # Clear stale destination data, preserve route-agnostic fields
            resolved = update_context_for_destination_change(resolved, new_dest)

    # ── Traveler count: current message overrides history ──
    traveler_match = re.search(
        r"\b(just\s+me|solo|alone|1\s+person|one\s+person|(\d+)\s*(?:travell?ers?|persons?|peoples?|pax))\b",
        q
    )
    if traveler_match:
        if "just me" in traveler_match.group(0) or "solo" in traveler_match.group(0) or "alone" in traveler_match.group(0) or "1 person" in traveler_match.group(0) or "one person" in traveler_match.group(0):
            resolved["travelers"] = 1
        elif traveler_match.group(2):
            resolved["travelers"] = int(traveler_match.group(2))

    # ── Budget update from current message ──
    budget_match = re.search(r"(?:budget|spend|under|within)\s*(?:of\s*)?(?:₹|rs\.?\s*)?([\d,]+)(?:k)?", q)
    if budget_match:
        amount_str = budget_match.group(1).replace(",", "")
        amount = int(amount_str)
        if "k" in q[budget_match.start():budget_match.end()+2]:
            amount *= 1000
        if amount > 500:  # sanity check — ignore very small numbers
            resolved.setdefault("budget_per_person", amount)

    # ── Destination from history (only if still missing after change check) ──
    if not resolved.get("destination") or resolved.get("destination") == "your destination":
        for entry in reversed(history[-10:]):
            text = entry.get("text", "").lower()
            dest_match = re.search(
                r"\b(goa|visakhapatnam|vizag|hyderabad|mumbai|delhi|jaipur|kerala|bali|paris|tokyo|bangkok|singapore|dubai|thailand|japan|maldives)\b",
                text
            )
            if dest_match:
                dest = dest_match.group(1)
                if dest == "vizag":
                    dest = "visakhapatnam"
                resolved.setdefault("destination", dest.title())
                break

    # ── Pronoun resolution ('there', 'it', 'that place') ──
    if any(k in q for k in [" there", " it ", "that place", "for there"]) and not resolved.get("destination"):
        for entry in reversed(history[-6:]):
            text = entry.get("text", "")
            dest_match = re.search(
                r"\b(Goa|Visakhapatnam|Hyderabad|Mumbai|Delhi|Jaipur|Kerala|Bali|Paris|Tokyo|Bangkok|Singapore|Dubai|Thailand|Japan)\b",
                text
            )
            if dest_match:
                resolved.setdefault("destination", dest_match.group(1))
                break

    # ── Traveler count from history (if not set by current message) ──
    if not resolved.get("travelers"):
        for entry in reversed(history[-10:]):
            m = re.search(r"\b(\d+)\s*(travell?ers?|persons?|peoples?|pax)\b", entry.get("text", "").lower())
            if m:
                resolved.setdefault("travelers", int(m.group(1)))
                break

    return resolved


# ─── Context Formatter for AI Prompting ──────────────────────────────────────

def _format_trip_context_for_llm(ctx: dict) -> str:
    """Formats the comprehensive trip context into structured plain text for the AI."""
    if not ctx:
        return "No specific trip plan is currently loaded. Assist the user with general travel advice."

    dest = ctx.get("destination", "Unknown")
    start_loc = ctx.get("start_location", "Unknown")
    start_date = ctx.get("start_date", "N/A")
    end_date = ctx.get("end_date", "N/A")
    num_days = ctx.get("num_days", "N/A")
    travelers = ctx.get("travelers", 2)
    currency = ctx.get("currency", "INR")

    ba = ctx.get("budget_analysis", {})
    est_total = ba.get("total_estimated_trip_cost", "N/A")
    avail_budget = ba.get("available_budget_total", "N/A")
    budget_status = ba.get("budget_status", "N/A")
    cats = ba.get("categories", {})

    budget_text = (
        f"Estimated Total: {currency} {est_total} | Available: {currency} {avail_budget} | Status: {budget_status}\n"
        f"  - Transportation: {currency} {cats.get('transportation', {}).get('total', 'N/A')}\n"
        f"  - Accommodation: {currency} {cats.get('accommodation', {}).get('total', 'N/A')}\n"
        f"  - Food & Dining: {currency} {cats.get('food', {}).get('total', 'N/A')}\n"
        f"  - Sightseeing: {currency} {cats.get('sightseeing', {}).get('total', 'N/A')}\n"
        f"  - Miscellaneous: {currency} {cats.get('miscellaneous', {}).get('total', 'N/A')}"
    )

    itin_days = ctx.get("itinerary", [])
    itin_lines = []
    for d in itin_days:
        d_num = d.get("day_number", "?")
        d_date = d.get("date_formatted", d.get("date", ""))
        m_name = d.get("morning", {}).get("name", "Rest") if d.get("morning") else "Rest"
        a_name = d.get("afternoon", {}).get("name", "Rest") if d.get("afternoon") else "Rest"
        e_name = d.get("evening", {}).get("name", "Rest") if d.get("evening") else "Rest"
        lunch = d.get("suggested_food_stop", "")
        itin_lines.append(
            f"Day {d_num} ({d_date}): Morning: {m_name} | Afternoon: {a_name} | Evening: {e_name} | Lunch: {lunch}"
        )

    itin_text = "\n".join(itin_lines) if itin_lines else "No daily schedule available."

    trans_options = ctx.get("transportation_comparison", {}).get("options", [])
    trans_lines = [
        f"{o.get('mode')}: {currency} {o.get('one_way_total_inr', 0):,.0f} one-way | {o.get('duration_formatted', 'N/A')}"
        for o in trans_options if o.get("available", True)
    ]

    weather = ctx.get("weather", {})
    weather_text = (
        f"Temperature: {weather.get('temperature')}°C | Condition: {weather.get('condition')} | "
        f"Humidity: {weather.get('humidity')}% | Advice: {', '.join(weather.get('travel_advice', []))}"
        if weather.get("available") else "Forecast unavailable."
    )

    return (
        f"=== CURRENT TRIP CONTEXT ===\n"
        f"Destination: {dest}\n"
        f"Starting Location: {start_loc}\n"
        f"Dates: {start_date} to {end_date} ({num_days} days)\n"
        f"Travellers: {travelers}\n\n"
        f"--- BUDGET STATUS ---\n{budget_text}\n\n"
        f"--- TRANSPORT MODES ---\n{chr(10).join(trans_lines) if trans_lines else 'No transport data available.'}\n\n"
        f"--- WEATHER FORECAST ---\n{weather_text}\n\n"
        f"--- DAILY ITINERARY ---\n{itin_text}\n"
        f"============================"
    )


def _build_ai_system_prompt(ctx: dict, intents: list[str], enriched_data: dict) -> str:
    """Build the system prompt injecting all relevant real-time data."""
    dest = ctx.get("destination", "the destination")
    trip_ctx = _format_trip_context_for_llm(ctx)

    search_ctx = ""
    if enriched_data.get("search_results"):
        from services.search_service import format_search_results_as_context
        search_ctx = "\n\n" + format_search_results_as_context(enriched_data["search_results"])

    weather_ctx = ""
    if enriched_data.get("live_weather"):
        w = enriched_data["live_weather"]
        weather_ctx = (
            f"\n\n[LIVE WEATHER DATA — {dest}]\n"
            f"Temperature: {w.get('temperature')}°C | Condition: {w.get('condition')} | "
            f"Humidity: {w.get('humidity')}% | Wind: {w.get('wind_speed_kmh')} km/h\n"
            f"Source: {w.get('provider', 'Open-Meteo')}"
        )

    currency_ctx = ""
    if enriched_data.get("currency_rates"):
        cr = enriched_data["currency_rates"]
        rates = cr.get("rates", {})
        currency_ctx = (
            f"\n\n[LIVE EXCHANGE RATES from INR — Source: {cr.get('source', 'unknown')}, Updated: {cr.get('updated', 'unknown')}]\n"
            + "\n".join([f"1 INR = {v:.4f} {k}" for k, v in list(rates.items())[:8]])
        )

    return (
        f"You are TripWise AI, an expert, friendly travel planning assistant with access to real-time data.\n\n"
        f"RULES:\n"
        f"1. Answer the user's question DIRECTLY — be conversational and specific.\n"
        f"2. Use the TRIP CONTEXT below to give personalised answers about their actual itinerary.\n"
        f"3. Use WEB SEARCH RESULTS if provided — cite URLs when referencing them, never invent sources.\n"
        f"4. Use LIVE WEATHER DATA if provided — clearly label it as live/real-time.\n"
        f"5. Use CURRENCY RATES if provided — show the update date.\n"
        f"6. Never invent prices, opening hours, or travel times — say 'I don't have live data on that' if unsure.\n"
        f"7. For follow-up questions using 'there', 'it', 'that place' — use the destination from context.\n"
        f"8. Keep responses concise but complete. Use bullet points and **bold** for key facts.\n"
        f"9. Admit when information is unavailable rather than guessing.\n\n"
        f"{trip_ctx}"
        f"{weather_ctx}"
        f"{currency_ctx}"
        f"{search_ctx}"
    )


# ─── Main Entry Point ────────────────────────────────────────────────────────

def generate_chat_response(
    message: str,
    conversation_history: list[dict] | None = None,
    trip_context: dict | None = None,
    history: list[dict] | None = None,
) -> dict:
    """
    Main chatbot response generator.

    Returns:
        {
            "reply": str,
            "provider": str,
            "source_indicator": str,  # "live_ai" | "ollama" | "offline_intelligence"
            "search_sources": list[dict],
            "data_labels": list[str],
            "updated_context": dict,
        }
    """
    msg_clean = message.strip()
    hist = conversation_history if conversation_history is not None else (history or [])
    ctx = trip_context or {}

    # Resolve implicit context from conversation history (handles dest change, traveler updates)
    ctx = _resolve_context_from_history(msg_clean, hist, ctx)

    # Classify intent
    intents = classify_intent(msg_clean, hist)
    logger.info("Message: %r | Intents: %s", msg_clean[:80], intents)

    # Fetch enriched data based on intents
    enriched = _fetch_enriched_data(msg_clean, ctx, intents)

    # Check which live AI backends are configured
    has_gemini = bool(os.getenv("GEMINI_API_KEY", "").strip() or GEMINI_API_KEY)
    has_openai = bool(os.getenv("OPENAI_API_KEY", "").strip() or OPENAI_API_KEY)
    ollama_url, _ = _get_ollama_config()
    has_ollama = bool(ollama_url and _is_ollama_available(ollama_url))
    has_any_ai = has_gemini or has_openai or has_ollama

    # If any live AI backend is configured, attempt AI response
    if has_any_ai:
        system_prompt = _build_ai_system_prompt(ctx, intents, enriched)

        # 1. Try Gemini (free tier)
        if has_gemini:
            ai_reply = _call_gemini(system_prompt, msg_clean, hist)
            if ai_reply:
                model_name = os.getenv("GEMINI_MODEL", "").strip() or GEMINI_MODEL or "gemini-2.5-flash"
                return _build_response(
                    ai_reply, f"Google Gemini ({model_name})", "live_ai", enriched, ctx
                )

        # 2. Try local Ollama (if configured and running)
        if has_ollama:
            ollama_reply = _call_ollama(system_prompt, msg_clean, hist)
            if ollama_reply:
                _, mod = _get_ollama_config()
                return _build_response(
                    ollama_reply, f"Local Ollama ({mod})", "ollama", enriched, ctx
                )

        # 3. Optional OpenAI if user explicitly provided a key
        if has_openai:
            openai_key = os.getenv("OPENAI_API_KEY", "").strip() or OPENAI_API_KEY
            openai_reply = _call_openai(system_prompt, msg_clean, hist, openai_key)
            if openai_reply:
                return _build_response(
                    openai_reply, "OpenAI GPT-4o-mini", "live_ai", enriched, ctx
                )

    # Permanent fallback: Offline expert travel intelligence engine
    offline_reply = _expert_offline_agent(msg_clean, hist, ctx, enriched)
    return _build_response(
        offline_reply, "TripWise Built-in Travel Intelligence Engine (Active)", "offline_intelligence", enriched, ctx
    )


def _build_response(
    reply: str,
    provider: str,
    source_indicator: str,
    enriched: dict,
    updated_ctx: dict | None = None,
) -> dict:
    """Build the final response dictionary with source links and metadata."""
    result: dict = {
        "reply": reply,
        "provider": provider,
        "source_indicator": source_indicator,
        "data_labels": enriched.get("data_labels", []),
    }
    if updated_ctx is not None:
        result["updated_context"] = updated_ctx
    if enriched.get("search_results"):
        result["search_sources"] = [
            {"title": r.get("title", "")[:80], "url": r.get("url", "")}
            for r in enriched["search_results"][:3]
            if r.get("url")
        ]
    return result


def _fetch_enriched_data(message: str, ctx: dict, intents: list[str]) -> dict:
    """
    Calls real-time services based on classified intents.
    Returns a dict with enriched data for injection into the AI prompt or offline engine.
    """
    enriched: dict = {"data_labels": []}
    dest = ctx.get("destination", "")

    # 1. Live weather
    if Intent.WEATHER in intents and dest:
        try:
            from services.weather_service import get_weather_for_destination
            w = get_weather_for_destination(dest, ctx.get("start_date"), ctx.get("end_date"))
            if w.get("available"):
                enriched["live_weather"] = w
                enriched["data_labels"].append(
                    f"🌤️ Live weather from {w.get('provider', 'Open-Meteo')}"
                )
        except Exception as exc:
            logger.warning("Weather fetch failed: %s", exc)

    # 2. Currency rates
    if Intent.CURRENCY in intents:
        try:
            cr = _get_free_exchange_rates()
            if cr.get("rates"):
                enriched["currency_rates"] = cr
                enriched["data_labels"].append(
                    f"💱 Exchange rates from {cr.get('source', 'Frankfurter.app')} (updated: {cr.get('updated', 'unknown')})"
                )
        except Exception as exc:
            logger.warning("Currency fetch failed: %s", exc)

    # 3. Web search (DuckDuckGo free search)
    if Intent.SEARCH in intents and dest:
        try:
            from services.search_service import web_search, should_web_search
            if should_web_search(message):
                q = message.lower()
                if any(k in q for k in ["open", "hours", "entry fee", "ticket"]):
                    search_query = f"{dest} tourist attractions opening hours entry fee 2025"
                elif any(k in q for k in ["visa", "passport"]):
                    search_query = f"Indian passport visa {dest} requirements 2025"
                elif any(k in q for k in ["festival", "event"]):
                    search_query = f"{dest} festivals events 2025 dates"
                elif any(k in q for k in ["restaurant", "eat", "food"]):
                    search_query = f"best restaurants {dest} 2025 must eat"
                elif any(k in q for k in ["news", "travel advisory"]):
                    search_query = f"{dest} travel news advisory 2025"
                else:
                    search_query = f"{dest} {message[:60]} travel information 2025"

                results = web_search(search_query, max_results=4)
                if results:
                    enriched["search_results"] = results
                    enriched["data_labels"].append(f"🔍 DuckDuckGo search: {search_query[:60]}")
        except Exception as exc:
            logger.warning("Web search failed: %s", exc)

    return enriched


# ─── Offline Expert Engine (Phase 5, 6 & 7) ──────────────────────────────────

def _expert_offline_agent(query: str, history: list[dict], ctx: dict, enriched: dict = None) -> str:
    """
    Context-aware offline travel expert engine.
    Uses trip-specific data, conversation history, and enriched service data.
    """
    if enriched is None:
        enriched = {}
    q = query.lower()
    dest = ctx.get("destination", "your destination")
    dest_key = dest.lower()
    start_loc = ctx.get("start_location", "your starting point")
    travelers = ctx.get("travelers", 2)
    currency = ctx.get("currency", "INR")
    itinerary = ctx.get("itinerary", [])
    attractions_summary = ctx.get("attractions_summary", [])
    budget_analysis = ctx.get("budget_analysis", {})

    # ── 0. Destination Change ──
    new_dest_entity, is_dest_change = extract_destination_entity(query)
    if is_dest_change and new_dest_entity:
        # User explicitly requested or switched to a destination
        followup = ""
        if ctx.get("start_location"):
            followup = f" from **{ctx.get('start_location')}**"
        return (
            f"Sure! Let's plan a trip to **{new_dest_entity}**{followup}. 🌍\n\n"
            f"I've cleared your previous itinerary data so we start fresh.\n\n"
            f"To get started, tell me:\n"
            f"• 📅 **How many days** are you planning?\n"
            f"• 👥 **How many travellers**?\n"
            f"• 💰 **What's your budget** (per person or total)?\n\n"
            f"Or just ask me about attractions, weather, best time to visit, or local food!"
        )

    # ── 1. Greeting ──
    q_stripped = q.strip().rstrip("!?.,")
    is_greeting_message = (
        q_stripped in {"hi", "hii", "hiii", "hey", "hello", "yo", "namaste", "hola", "greetings", "hi!", "hello!", "hey!"}
        or any(k in q for k in ["hello", "hi ", "hey ", "good morning", "good evening", "good afternoon", "namaste", "hola"])
    )
    if is_greeting_message:
        has_trip = bool(itinerary) or bool(ctx.get("budget_analysis"))
        if dest != "your destination" and has_trip:
            # Trip already generated
            return (
                f"Hey! 👋 I'm **TripWise AI** — your trip to **{dest}** is loaded and ready.\n\n"
                f"Ask me anything — Day plans, budget, weather, food, packing, transport, or tips!\n"
                f"*(e.g. \"What's on Day 2?\" · \"How can I cut costs?\" · \"What food should I try?\")*"
            )
        elif dest != "your destination":
            # Destination set but no itinerary yet
            return (
                f"Hi! I'm **TripWise AI** — ready to continue planning your trip to **{dest}**? 🗺️\n\n"
                f"What would you like to know — weather, best time to visit, transport options, or shall we generate the full itinerary?"
            )
        else:
            # No destination set at all
            return (
                f"Hey! Welcome to **TripWise AI** 👋\n\n"
                f"I'm your personal travel planning assistant. Where are you thinking of travelling?\n\n"
                f"*(Tell me a destination and I'll help you plan the perfect trip!)*"
            )

    # ── 2. Currency (with enriched data) ──
    if any(k in q for k in ["currency", "exchange rate", "convert", "dollar", "euro", "pound", "usd", "eur", "gbp", "how much is"]):
        cr = enriched.get("currency_rates") or _get_free_exchange_rates()
        rates = cr.get("rates", {})
        updated = cr.get("updated", "unknown")
        source = cr.get("source", "Frankfurter.app")

        lines = [f"**💱 Exchange Rates (Base: INR)**\n*Source: {source} | Updated: {updated}*\n"]
        mentioned = []
        for code, name in [("USD", "US Dollar"), ("EUR", "Euro"), ("GBP", "British Pound"),
                            ("SGD", "Singapore Dollar"), ("AED", "UAE Dirham"), ("JPY", "Japanese Yen"), ("THB", "Thai Baht")]:
            if code.lower() in q or name.lower() in q:
                mentioned.append((code, name))

        show_codes = mentioned if mentioned else [("USD", "US Dollar"), ("EUR", "Euro"), ("GBP", "British Pound"), ("SGD", "Singapore Dollar"), ("AED", "UAE Dirham"), ("JPY", "Japanese Yen")]
        for code, name in show_codes:
            if code in rates:
                inv = round(1.0 / rates[code], 2) if rates[code] else 0
                lines.append(f"• 1 INR = {rates[code]:.4f} {code}  _(1 {code} = ₹{inv})_")

        amt_match = re.search(r"(?:₹|rs\.?\s*)(\d[\d,]*)", q)
        if not amt_match:
            amt_match = re.search(r"(\d[\d,]+)\s*(?:rupee|inr)", q)
        if amt_match:
            amount = float(amt_match.group(1).replace(",", ""))
            lines.append(f"\n**Quick Conversion for ₹{amount:,.0f}:**")
            for code in ["USD", "EUR", "GBP"]:
                if code in rates:
                    lines.append(f"• {code}: {amount * rates[code]:,.2f}")

        lines.append("\n⚠️ *Rates are for reference only. Check your bank for actual transfer rates.*")
        return "\n".join(lines)

    # ── 3. Weather ──
    if any(k in q for k in ["weather", "temperature", "forecast", "climate", "rain", "hot", "cold", "humidity", "wind", "sunny"]):
        w = enriched.get("live_weather") or ctx.get("weather", {})
        if w and w.get("available"):
            search_note = ""
            if enriched.get("search_results"):
                top = enriched["search_results"][0]
                snippet = top.get("snippet", "")[:150]
                url = top.get("url", "")
                search_note = f"\n\n🔍 *Additional info: {snippet}*  [Source: {url}]"
            advice = "\n• " + "\n• ".join(w.get("travel_advice", []))
            return (
                f"**Live Weather for {dest}:**\n\n"
                f"• 🌡️ Temperature: **{w.get('temperature')}°C**\n"
                f"• ☁️ Conditions: **{w.get('condition')}**\n"
                f"• 💧 Humidity: **{w.get('humidity')}%**\n"
                f"• 💨 Wind Speed: **{w.get('wind_speed_kmh', w.get('wind_speed', 10))} km/h**\n"
                f"• 🌐 Source: *{w.get('provider', 'Open-Meteo')}*\n\n"
                f"**Travel Advice:**{advice}"
                f"{search_note}"
            )
        for key, data in DESTINATION_BEST_TIME.items():
            if key in dest_key:
                return (
                    f"Live weather data isn't loaded for {dest} right now.\n\n"
                    f"**Seasonal Guide:**\n"
                    f"• Best months: **{data['best_months']}**\n"
                    f"• {data['notes']}\n\n"
                    f"💡 Generate a trip plan to get current live weather from Open-Meteo (free, no key needed)."
                )
        return f"Weather forecasts for {dest} weren't available right now. Check the **🌤 Weather** tab in your itinerary or visit weather.com."

    # ── 4. Best Time to Visit ──
    if any(k in q for k in ["best time", "best season", "when to visit", "when should i", "what month", "good time", "ideal time", "right time", "which month"]):
        for key, data in DESTINATION_BEST_TIME.items():
            if key in dest_key or dest_key in key:
                return (
                    f"**Best Time to Visit {dest}:**\n\n"
                    f"🏆 **Peak Season**: {data['peak']}\n"
                    f"⭐ **Best Months**: {data['best_months']}\n"
                    f"⚠️ **Avoid**: {data['avoid']}\n\n"
                    f"🎉 **Local Festivals**: {data.get('festivals', 'Various regional festivals throughout the year')}\n\n"
                    f"📝 **Tips**: {data['notes']}"
                )
        return (
            f"**Best Time to Visit {dest}:**\n\n"
            f"Generally, **October to March** is the best time for most Indian destinations.\n\n"
            f"• **Avoid** peak summer (April–June) due to heat.\n"
            f"• **Monsoon** (June–September) brings lush greenery but heavy rains.\n"
            f"• Check local festival calendars — visiting during a major festival adds an unforgettable experience.\n\n"
            f"For {dest} specifically, check forecasts 2–3 weeks before departure."
        )

    # ── 5. Transport ──
    if any(k in q for k in ["transport", "how to get", "how do i get", "getting there", "travel from", "reach", "flight", "train", "bus", "taxi", "cab", "drive", "car", "auto", "metro"]):
        trans_comp = ctx.get("transportation_comparison", {})
        options = trans_comp.get("options", [])
        available = [o for o in options if o.get("available", True)]

        if available:
            lines = [f"**Transport Options from {trans_comp.get('start_location', start_loc)} to {trans_comp.get('destination', dest)}:**\n"]
            lines.append(f"🗺️ Road: ~{trans_comp.get('road_distance_km', 'N/A')} km | Air: ~{trans_comp.get('air_distance_km', 'N/A')} km\n")
            for opt in available:
                badges_str = " ".join([f"[{b}]" for b in opt.get("badges", [])])
                one_way = opt.get("one_way_total_inr", 0)
                round_trip = opt.get("return_total_inr", 0)
                lines.append(
                    f"{opt.get('icon', '🚗')} **{opt['mode']}** {badges_str}\n"
                    f"   • Duration: {opt.get('duration_formatted', 'N/A')}\n"
                    f"   • One-way (group): {currency} {one_way:,.0f} | Round-trip: {currency} {round_trip:,.0f}\n"
                    f"   • {opt.get('notes', '')}"
                )
            lines.append(f"\n💡 *Compare all 5 options in detail under the **🚆 Transport Comparison** tab.*")
            return "\n\n".join(lines)
        return (
            f"**Getting to {dest} from {start_loc}:**\n\n"
            f"The main options typically include:\n"
            f"• ✈️ **Flights**: Fastest — book 2–4 weeks ahead for best fares on Google Flights.\n"
            f"• 🚆 **Trains**: Comfortable — book on IRCTC (irctc.co.in). AC 3-Tier is a good balance.\n"
            f"• 🚌 **Buses**: Budget-friendly overnight sleepers. Book on redBus.\n"
            f"• 🚕 **Cabs**: Door-to-door convenience (Savaari or MakeMyTrip Cabs).\n\n"
            f"Generate a full itinerary to see personalised transport cost comparisons for your route."
        )

    # ── 6. Budget ──
    if any(k in q for k in ["budget", "cost", "how much", "price", "cheaper", "save money", "shortfall", "expensive", "reduce", "afford", "money", "rupee", "₹"]):
        est_cost = budget_analysis.get("total_estimated_trip_cost", 0)
        avail = budget_analysis.get("available_budget_total", 0)
        cats = budget_analysis.get("categories", {})
        accom_cost = cats.get("accommodation", {}).get("total", 0)
        trans_cost = cats.get("transportation", {}).get("total", 0)
        food_cost = cats.get("food", {}).get("total", 0)
        sight_cost = cats.get("sightseeing", {}).get("total", 0)
        misc_cost = cats.get("miscellaneous", {}).get("total", 0)

        num_match = re.search(r"[\d,]+", q)
        target_num_str = f" to {currency} {num_match.group(0)}" if num_match else ""

        if est_cost and avail:
            return (
                f"**Budget Analysis for {dest}**{target_num_str}:\n\n"
                f"• **Estimated Trip Cost**: {currency} {est_cost:,.0f}\n"
                f"• **Your Budget**: {currency} {avail:,.0f}\n"
                f"• **Status**: {budget_analysis.get('status_label', budget_analysis.get('budget_status', 'N/A'))}\n\n"
                f"**Cost Breakdown:**\n"
                f"• 🚆 Transportation: {currency} {trans_cost:,.0f}\n"
                f"• 🏨 Accommodation: {currency} {accom_cost:,.0f}\n"
                f"• 🍲 Food & Dining: {currency} {food_cost:,.0f}\n"
                f"• 🎟️ Sightseeing: {currency} {sight_cost:,.0f}\n"
                f"• 🛡️ Emergency Buffer: {currency} {misc_cost:,.0f}\n\n"
                f"**Ways to Reduce Costs:**\n"
                f"1. **Accommodation** ({currency} {accom_cost:,.0f}): Switch to hostels or guesthouses — saves 35–50%.\n"
                f"2. **Transportation** ({currency} {trans_cost:,.0f}): Choose trains/buses over flights/cabs — saves 40–60%.\n"
                f"3. **Food** ({currency} {food_cost:,.0f}): Eat at local thali restaurants and dhabas — saves 30–50%.\n"
                f"4. **Sightseeing**: Prioritise free attractions (beaches, parks, heritage walks).\n\n"
                f"⚠️ All costs are independent estimates — regenerate with updated preferences for revised numbers."
            )
        if "thailand" in dest_key or "bangkok" in dest_key:
            return (
                f"**Budget Optimization for Thailand**{target_num_str}:\n\n"
                f"Here are practical ways to reduce your Thailand travel costs (with typical market estimates):\n\n"
                f"1. 🍲 **Street Food & Night Markets**: Eat at local night markets (Pad Thai, Som Tum for 50–100 THB / ₹120–240 estimated) rather than tourist seafood restaurants — saves 50–60%.\n"
                f"2. 🚆 **Public Transit Over Taxis**: Use the BTS Skytrain, MRT subway, and Chao Phraya express boats (estimated 15–60 THB / ₹35–150) instead of unmetered tuk-tuks or tourist vans.\n"
                f"3. 🏨 **Accommodation**: Choose modern boutique guesthouses or hostels (estimated ₹800–1,500/night) in central areas near transit stations (Sukhumvit, Silom, Nimman) — saves 40% vs international chains.\n"
                f"4. ✈️ **Budget Airlines**: Fly low-cost carriers (AirAsia, Scoot, IndiGo) and book domestic flights 3–4 weeks in advance (typically ₹2,000–3,500 one-way estimated fare).\n"
                f"5. 🎟️ **Sightseeing**: Prioritize temples with low published admission (Wat Arun ₹250, Wat Pho ₹500) and free public spaces like Chatuchak Market, Lumpini Park, and public beaches.\n\n"
                f"⚠️ *Note: Admission fees reflect official published tourist rates. Food, lodging, transit, and flight fares are realistic market estimates subject to seasonal variation — check live booking platforms for exact dates.*"
            )
        return (
            f"**Budget Guide for {dest}**{target_num_str}:\n\n"
            f"Generate a full trip plan first for a detailed cost breakdown. Rough guides:\n\n"
            f"• 🏨 **Accommodation**: ₹500–800/night (hostel) | ₹1,200–2,000/night (budget hotel) | ₹3,000–6,000/night (mid-range)\n"
            f"• 🚗 **Transportation**: ₹500–2,000/person (bus/train one-way) | ₹5,000–12,000 (flight)\n"
            f"• 🍲 **Food & Dining**: ₹150–300/meal (local) | ₹400–800/meal (restaurant)\n"
            f"• 🎟️ **Sightseeing**: ₹0–500/attraction\n\n"
            f"**Top Ways to Save:**\n"
            f"1. **Accommodation** — Book hostels or guesthouses (saves 35–50% vs hotels)\n"
            f"2. **Transportation** — Trains and buses beat flights and private cabs by 40–60%\n"
            f"3. **Food** — Eat at local eateries and dhabas instead of tourist restaurants\n\n"
            f"💡 Generate your personalised trip plan above for exact {dest} cost estimates."
        )

    # ── 7. Itinerary Modification (CHECKED BEFORE DAY RECALL) ──
    if any(k in q for k in [
        "replace", "change", "swap", "substitute", "instead of",
        "alternative", "another option", "different option", "what else",
        "modify", "switch"
    ]):
        target_day = 1
        day_match = re.search(r"\bday\s*(\d+)\b", q)
        if day_match:
            target_day = int(day_match.group(1))
        else:
            ordinals = {
                "first": 1, "1st": 1, "second": 2, "2nd": 2,
                "third": 3, "3rd": 3, "fourth": 4, "4th": 4,
                "fifth": 5, "5th": 5, "sixth": 6, "6th": 6
            }
            for word, num in ordinals.items():
                if word in q:
                    target_day = num
                    break
            else:
                for h in reversed(history[-6:]):
                    h_text = h.get("text", "").lower()
                    m_d = re.search(r"\bday\s*(\d+)\b", h_text)
                    if m_d:
                        target_day = int(m_d.group(1))
                        break

        # Parse slot
        if "afternoon" in q:
            slot_name = "afternoon"
        elif "morning" in q:
            slot_name = "morning"
        elif "evening" in q:
            slot_name = "evening"
        else:
            slot_name = "afternoon"
            for h in reversed(history[-4:]):
                ht = h.get("text", "").lower()
                if "morning" in ht:
                    slot_name = "morning"
                    break
                elif "evening" in ht:
                    slot_name = "evening"
                    break
                elif "afternoon" in ht:
                    slot_name = "afternoon"
                    break

        curr_name = "the scheduled activity"
        for d in itinerary:
            if d.get("day_number") == target_day and d.get(slot_name):
                curr_name = d[slot_name].get("name", curr_name)
                break

        scheduled_in_day = set()
        for d in itinerary:
            if d.get("day_number") == target_day:
                for s in ["morning", "afternoon", "evening"]:
                    if d.get(s):
                        scheduled_in_day.add(d[s].get("name"))

        candidates = [a for a in attractions_summary if a.get("name") not in scheduled_in_day]
        if candidates:
            alt = candidates[0]
            alt2 = candidates[1] if len(candidates) > 1 else None
            fee_note = "*Free entry* ✓" if alt.get("entry_fee_inr", 0) == 0 else f"*Entry: ₹{alt.get('entry_fee_inr')} per person*"
            reply = (
                f"For **Day {target_day} {slot_name.capitalize()}** (currently: *{curr_name}*), "
                f"here are alternative recommendations in **{dest}**:\n\n"
                f"1. **{alt['name']}** ({alt.get('category', 'Landmark').title()})\n"
                f"   {alt.get('description', '')}\n"
                f"   {fee_note}\n"
            )
            if alt2:
                fee2 = "*Free entry* ✓" if alt2.get("entry_fee_inr", 0) == 0 else f"*Entry: ₹{alt2.get('entry_fee_inr')} per person*"
                reply += (
                    f"\n2. **{alt2['name']}** ({alt2.get('category', 'Landmark').title()})\n"
                    f"   {alt2.get('description', '')}\n"
                    f"   {fee2}\n"
                )
            reply += (
                f"\n💡 To apply changes with recalculated routes and costs, "
                f"update your interest categories in the planner and regenerate the itinerary."
            )
            return reply
        else:
            return (
                f"All standard attractions for **{dest}** are already included in your Day {target_day} schedule. "
                f"As an alternative recommendation for Day {target_day} {slot_name}, consider a relaxed local heritage walk, "
                f"exploring nearby artisan markets, or enjoying sunset at a beachside cafe."
            )

    # ── 8. Day Recall ──
    day_match = re.search(r"\bday\s*(\d+)\b", q)
    if not day_match:
        ordinals = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7}
        for word, num in ordinals.items():
            if f"{word} day" in q or f"day {word}" in q:
                day_match = type("Match", (), {"group": lambda self, x, _n=num: str(_n)})()
                break

    if day_match:
        target_day = int(day_match.group(1))
        matching_days = [d for d in itinerary if d.get("day_number") == target_day]
        if matching_days:
            day = matching_days[0]
            if day.get("is_rest_day"):
                return (
                    f"**Day {target_day}** ({day.get('date_formatted', '')}) — **Leisure & Exploration Day:**\n\n"
                    f"• {day.get('rest_day_note', 'Free day for leisure and exploration.')}\n"
                    f"• **Morning**: {day.get('morning', {}).get('name', 'Relaxed Morning')}\n"
                    f"• **Afternoon**: {day.get('afternoon', {}).get('name', 'Local Market Discovery')}\n"
                    f"• **Evening**: {day.get('evening', {}).get('name', 'Sunset Promenade & Dinner')}\n\n"
                    f"💡 Great day to revisit a favourite spot or try a local cooking class."
                )
            m = day.get("morning", {})
            a = day.get("afternoon", {})
            e = day.get("evening", {})
            m_route = day.get("route_morning_to_afternoon", {})
            a_route = day.get("route_afternoon_to_evening", {})
            return (
                f"**Day {target_day}** in **{dest}** ({day.get('date_formatted', '')}):\n\n"
                f"🌅 **Morning (09:00–12:00)**: **{m.get('name', 'Sightseeing')}** ({m.get('category', 'Historical')})\n"
                f"  {m.get('description', '')}\n"
                f"  *Duration: {m.get('visit_duration', '2 hours')} | Hours: {m.get('opening_hours', '09:00–18:00')}*\n\n"
                f"  🚗 Travel to afternoon: ~{m_route.get('distance_km', 4)} km ({m_route.get('duration_formatted', '15 min')})\n\n"
                f"☀️ **Afternoon (12:30–15:30)**: **{a.get('name', 'Sightseeing')}** ({a.get('category', 'Nature')})\n"
                f"  {a.get('description', '')}\n"
                f"  🍲 Lunch: {day.get('suggested_food_stop', 'Local cafe nearby')}\n\n"
                f"  🚗 Travel to evening: ~{a_route.get('distance_km', 3)} km ({a_route.get('duration_formatted', '12 min')})\n\n"
                f"🌆 **Evening (16:30–19:30)**: **{e.get('name', 'Sightseeing')}** ({e.get('category', 'Culture')})\n"
                f"  {e.get('description', '')}\n\n"
                f"📍 Total driving distance: **~{day.get('day_total_route_km', 7)} km**"
            )
        elif itinerary:
            return f"Your trip covers {len(itinerary)} days. Day {target_day} is outside your planned itinerary duration."
        else:
            # Itinerary not yet generated in the planner (e.g. user just switched to Thailand)
            if "thailand" in dest_key or "bangkok" in dest_key:
                return (
                    f"You haven't generated a full daily schedule for **Thailand** yet, but here is a recommended "
                    f"**Day {target_day} (Bangkok Cultural Highlights)** schedule:\n\n"
                    f"🌅 **Morning (08:30–12:00)**: **The Grand Palace & Wat Phra Kaew**\n"
                    f"  Explore Thailand's most revered royal temple complex and the sacred 14th-century Emerald Buddha.\n"
                    f"  *Duration: 2.5 hours | Hours: 08:30–15:30 | Official Entry: ₹1,200 (500 THB)*\n\n"
                    f"☀️ **Afternoon (13:00–16:00)**: **Wat Pho & Chao Phraya River Longtail Boat Cruise**\n"
                    f"  Marvel at the 46m gold Reclining Buddha (Official Entry: ₹500 / 200 THB), then take a cross-river ferry (estimated ₹15 / 5 THB) to Wat Arun.\n"
                    f"  🍲 Lunch: Traditional Pad Thai and Tom Yum at Tha Tien riverside pier (estimated ₹150–300).\n\n"
                    f"🌆 **Evening (17:30–21:00)**: **Asiatique The Riverfront & Night Market**\n"
                    f"  Scenic waterfront promenade, artisan crafts, cultural shows, and street food dinner (Free entry, pay per meal/activity).\n\n"
                    f"💡 *Admission rates are official published tariffs; food and transit fares are market estimates. To generate your complete custom multi-day plan with automated driving routes, pick your dates in the planner above and click **'Generate Itinerary'**!*"
                )
            else:
                return (
                    f"You haven't generated a daily itinerary for **{dest}** yet.\n\n"
                    f"Tell me how many days you'd like to stay and your preferred travel dates, or click **'Generate Itinerary'** "
                    f"in the trip planner above to build a full Day {target_day} schedule with routes and maps!"
                )

    # ── 9. Attractions ──
    if any(k in q for k in ["places to visit", "suggest places", "what to visit", "top places", "attractions", "sightseeing", "must see", "must visit", "what to see", "tourist spots", "landmarks", "things to do"]) or re.search(r"\b(?:what\s+places|places\s+(?:to\s+visit|should\s+i\s+visit|can\s+i\s+visit)|what\s+to\s+visit|what\s+to\s+see|places\s+to\s+see)\b", q):
        attrs = attractions_summary
        if not attrs and dest and dest != "your destination":
            from services.attractions_service import get_attractions_for_destination
            loaded, _ = get_attractions_for_destination(dest)
            attrs = loaded

        if attrs:
            lines = [f"**Top Tourist Attractions in {dest}:**"]
            for a in attrs[:8]:
                fee_val = a.get('entry_fee_inr', a.get('fee', 0))
                fee_txt = "Free Entry" if fee_val == 0 else f"₹{fee_val} ticket"
                desc = a.get('description', a.get('desc', ''))[:100]
                lines.append(f"• **{a['name']}** ({a.get('category', 'Historical').title()} · {fee_txt})\n  {desc}...")
            lines.append("\n📍 All these can be explored on your interactive map with calculated driving routes.\n*(Admission fees reflect official published tariffs; food and transit costs are local estimates.)*")
            return "\n\n".join(lines)
        return (
            f"Generate a trip plan for {dest} first — TripWise will show you verified tourist attractions "
            f"with opening hours, entry fees, GPS coordinates, and driving routes between them."
        )

    # ── 10. Nearby Attractions ──
    if any(k in q for k in ["near", "closest to", "around", "nearby", "close to"]):
        ref_attr = None
        for a in attractions_summary:
            if a["name"].lower() in q or any(part in q for part in a["name"].lower().split() if len(part) > 4):
                ref_attr = a
                break
        if ref_attr and ref_attr.get("lat") and ref_attr.get("lon"):
            ref_lat, ref_lon = ref_attr["lat"], ref_attr["lon"]
            distances = []
            for other in attractions_summary:
                if other["name"] == ref_attr["name"]:
                    continue
                if other.get("lat") and other.get("lon"):
                    dlat = (other["lat"] - ref_lat) * 111.0
                    dlon = (other["lon"] - ref_lon) * 111.0 * math.cos(math.radians(ref_lat))
                    dist_km = round(math.sqrt(dlat * dlat + dlon * dlon), 1)
                    distances.append((other, dist_km))
            distances.sort(key=lambda x: x[1])
            lines = [f"Attractions close to **{ref_attr['name']}** in {dest}:"]
            for item, km in distances[:4]:
                fee = "Free" if item.get("entry_fee_inr", 0) == 0 else f"₹{item.get('entry_fee_inr')}"
                lines.append(f"• **{item['name']}** (~{km} km away) — *{item.get('category', 'Sightseeing').title()}* ({fee}): {item.get('description', '')[:90]}...")
            lines.append("\nCombine these on the same day to minimise travel time.")
            return "\n\n".join(lines)
        return "I couldn't identify a specific landmark to calculate distances from. Try: *'Which attractions are near Baga Beach?'*"

    # ── 11. Distance Between Two Attractions ──
    dist_match2 = re.search(r"distance\s+between\s+(.+?)\s+and\s+(.+?)(?:\?|$)", q, re.IGNORECASE)
    far_match = re.search(r"how\s+far\s+is\s+(.+?)\s+from\s+(.+?)(?:\?|$)", q, re.IGNORECASE)
    if dist_match2 or far_match:
        name_a = (dist_match2 or far_match).group(1).strip()
        name_b = (dist_match2 or far_match).group(2).strip()

        def find_attraction(name_query):
            name_q = name_query.lower()
            for a in attractions_summary:
                a_name = a["name"].lower()
                if name_q in a_name or a_name in name_q:
                    return a
                if len(set(name_q.split()) & set(a_name.split())) >= 1:
                    return a
            return None

        attr_a = find_attraction(name_a)
        attr_b = find_attraction(name_b)
        if attr_a and attr_b and attr_a.get("lat") and attr_b.get("lat"):
            dlat = (attr_b["lat"] - attr_a["lat"]) * 111.0
            dlon = (attr_b["lon"] - attr_a["lon"]) * 111.0 * math.cos(math.radians(attr_a["lat"]))
            dist_km = round(math.sqrt(dlat * dlat + dlon * dlon), 1)
            drive_min = max(5, int(dist_km / 25 * 60))
            return (
                f"📍 **Distance: {attr_a['name']} → {attr_b['name']}**\n\n"
                f"• **Straight-line distance**: ~{dist_km} km\n"
                f"• **Estimated drive time**: ~{drive_min} min (city traffic, ~25 km/h avg)\n\n"
                f"💡 Both attractions are in **{dest}** and can easily be visited on the same day."
            )

    # ── 12. Safety / Visa ──
    if any(k in q for k in ["visa", "passport", "entry", "safe", "safety", "dangerous", "crime", "emergency"]):
        intl_dest = any(k in dest_key for k in ["paris", "tokyo", "bali", "singapore", "london", "dubai", "new york", "rome", "bangkok"])
        search_note = ""
        if enriched.get("search_results"):
            top = enriched["search_results"][0]
            search_note = f"\n\n🔍 *Web search result: {top.get('snippet', '')[:180]}*  [Source: {top.get('url', '')}]"
        if intl_dest:
            return (
                f"**Travel Requirements for {dest}:**\n\n"
                f"🛂 **Visa**: Indian passport holders typically need a visa for {dest}. "
                f"Check the official embassy website or use VFS Global or iVisa for updated requirements.\n\n"
                f"🏥 **Travel Insurance**: Strongly recommended — covers medical emergencies, cancellations, and lost baggage.\n\n"
                f"🆘 **Emergency Numbers**: Note down local emergency services, embassy number, and hotel address.\n\n"
                f"🔒 **Safety Tips**:\n"
                f"• Keep digital and physical copies of your passport and visa.\n"
                f"• Use hotel safes for valuables.\n"
                f"• Register with your country's embassy for extended stays."
                f"{search_note}"
            )
        return (
            f"**Safety Information for {dest}, India:**\n\n"
            f"✅ {dest} is generally a safe destination for tourists.\n\n"
            f"• 👜 Keep bags close in crowded areas.\n"
            f"• 💳 Carry some cash — not all places accept cards.\n"
            f"• 🌊 Follow safety flags on beaches — red flags mean no swimming.\n"
            f"• 🏍️ If renting a bike/scooter, wear a helmet and carry your driving licence.\n"
            f"• 📱 Keep your phone charged and share your itinerary with family/friends.\n\n"
            f"Emergency numbers: Police **100** | Ambulance **102** | Fire **101** | Tourist Helpline **1800-11-1363**"
            f"{search_note}"
        )

    # ── 13. Food ──
    if any(k in q for k in ["food", "dish", "cuisine", "eat", "restaurant", "taste", "dining", "lunch", "dinner", "breakfast", "snack", "drink", "street food", "must eat"]):
        food_stops = [d.get("suggested_food_stop") for d in itinerary if d.get("suggested_food_stop")]
        sample_stops = list(dict.fromkeys(food_stops))[:3]
        stops_txt = "\n".join([f"• {s}" for s in sample_stops]) if sample_stops else "• Local cafes and street food near your planned attractions"

        food_info = {
            "thailand": "🍜 Pad Thai · Tom Yum Goong · Som Tum (Papaya Salad) · Green Curry · Mango Sticky Rice · Massaman Curry · Thai Iced Tea",
            "bangkok": "🍜 Pad Thai (Thip Samai) · Crab Omelette (Jay Fai) · Boat Noodles · Mango Sticky Rice · Grilled Pork Skewers (Moo Ping)",
            "goa": "🦞 Goan Fish Curry Rice · Prawn Balchao · Bebinca Dessert · Feni Cocktail · Fresh Seafood Platter",
            "visakhapatnam": "🦐 Andhra Prawn Fry · Murai Mixture · Bamboo Chicken (Araku) · Pesarattu · Bobbatlu Sweet",
            "hyderabad": "🍚 Hyderabadi Dum Biryani · Haleem · Osmania Biscuits · Irani Chai · Mirchi ka Salan",
            "paris": "🥐 Croissants · Crêpes · Steak Tartare · French Onion Soup · Macarons · Crème Brûlée",
            "tokyo": "🍱 Ramen · Sushi · Yakitori · Tempura · Matcha Sweets · Convenience Store Onigiri",
            "bali": "🍛 Nasi Goreng · Babi Guling · Satay · Jamu Herbal Drinks · Warungs (local eateries)",
            "mumbai": "🌮 Vada Pav · Pav Bhaji · Bhelpuri · Misal Pav · Bombay Sandwich · Juhu Beach Chaat",
            "jaipur": "🥘 Dal Baati Churma · Laal Maas · Ghevar · Pyaaz Kachori · Doodh Jalebi",
            "kerala": "🍌 Sadya Feast · Appam with Stew · Karimeen Pollichathu · Puttu · Kerala Prawn Curry"
        }

        dest_food = "Explore local eateries, street food stalls, and regional specialties"
        for key, val in food_info.items():
            if key in dest_key:
                dest_food = val
                break

        search_note = ""
        if enriched.get("search_results"):
            top = enriched["search_results"][0]
            search_note = f"\n\n🔍 *Web: {top.get('snippet', '')[:150]}*\n[Source: {top.get('url', '')}]"

        return (
            f"**Food & Dining in {dest}:**\n\n"
            f"🍽️ **Signature Dishes**: {dest_food}\n\n"
            f"**Your Itinerary's Recommended Food Stops:**\n{stops_txt}\n\n"
            f"**General Dining Tips:**\n"
            f"• Restaurants with high local foot traffic = freshest ingredients.\n"
            f"• Street food and local dhabas are cheaper and more authentic than tourist-facing restaurants.\n"
            f"• Reserve dinner at popular spots in advance, especially on weekends."
            f"{search_note}"
        )

    # ── 14. Tips ──
    if any(k in q for k in ["tips", "advice", "tricks", "suggest", "recommendation", "guide", "must know", "insider"]):
        for key, tips in DESTINATION_TIPS.items():
            if key in dest_key:
                tips_text = "\n".join([f"• {t}" for t in tips])
                return (
                    f"**Insider Tips for {dest}:**\n\n"
                    f"{tips_text}\n\n"
                    f"💬 Ask me about specific attractions, the best day to visit, or what to pack!"
                )
        return (
            f"**Travel Tips for {dest}:**\n\n"
            f"• Start each day early — popular attractions are less crowded in the morning.\n"
            f"• Keep a mix of cash and cards — smaller establishments may not accept cards.\n"
            f"• Download Google Maps offline for navigation without data costs.\n"
            f"• Carry a reusable water bottle — hydration is especially important in warmer climates.\n"
            f"• Respect local customs at temples and heritage sites (dress modestly, remove shoes where required).\n\n"
            f"Ask me about specific Days, food, weather, budget, or transport for more tailored advice!"
        )

    # ── 15. Packing ──
    if any(k in q for k in ["pack", "luggage", "wear", "clothes", "what to bring", "carry", "bag", "suitcase"]):
        weather = enriched.get("live_weather") or ctx.get("weather", {})
        temp = weather.get("temperature", 28) if weather else 28
        clothing_advice = "Lightweight, breathable cotton clothing" if temp > 22 else "Warm layered clothing and a good jacket"
        is_beach = any(k in dest_key for k in ["goa", "bali", "phuket", "vizag", "visakhapatnam", "kerala"])
        is_hill = any(k in dest_key for k in ["manali", "shimla", "darjeeling", "ooty", "munnar"])
        beach_note = "\n• **Beach Items**: Swimwear, flip-flops, beach towel, waterproof sunscreen (SPF 50+)." if is_beach else ""
        hill_note = "\n• **Cold Weather**: Thermal inners, a heavy jacket/down coat, and waterproof trekking shoes." if is_hill else ""
        return (
            f"**Packing Checklist for {dest}:**\n\n"
            f"• **Clothing**: {clothing_advice}, comfortable walking shoes/sneakers, and modest attire for temples.{beach_note}{hill_note}\n"
            f"• **Documents**: Passport/ID, return tickets (printed + digital), hotel confirmations, travel insurance.\n"
            f"• **Money**: Sufficient local currency (₹) + a backup card; notify your bank of travel.\n"
            f"• **Electronics**: 10,000+ mAh power bank, universal charger, earphones, offline maps downloaded.\n"
            f"• **Health**: Sunscreen SPF 50+, insect repellent, oral rehydration salts, personal medications, basic first aid.\n"
            f"• **Misc**: Reusable water bottle, travel umbrella/raincoat, small padlock for hostel lockers, day backpack."
        )

    # ── 16. Web Search Results (when specific web query made) ──
    if enriched.get("search_results") and not any(k in q for k in ["hello", "hi ", "hey "]):
        results = enriched["search_results"]
        lines = [f"**Search Results for your question about {dest}:**\n"]
        for r in results[:3]:
            snippet = r.get("snippet", "").strip()
            if snippet:
                lines.append(f"• {snippet[:200]}")
                if r.get("url"):
                    lines.append(f"  🔗 [Read more]({r['url']})")
            elif r.get("title"):
                lines.append(f"• {r['title']}")
                if r.get("url"):
                    lines.append(f"  🔗 [Read more]({r['url']})")
        lines.append(f"\n💡 *Web search powered by DuckDuckGo — no API key required.*")
        return "\n".join(lines)

    # ── 16b. Group Size / Traveller Count Update ──
    traveler_update = (
        re.search(r"^(?:for|we are|it's|party of|group of)\s*(\d+)\s*(?:travell?ers?|persons?|people|peoples?|pax)?\.?$", q)
        or re.search(r"^(\d+)\s*(?:travell?ers?|persons?|people|peoples?|pax)\.?$", q)
    )
    if traveler_update:
        count = int(traveler_update.group(1))
        return (
            f"Got it! I've updated your party size to **{count} travellers** for **{dest}**. 👥\n\n"
            f"• All transport options, hotel room allocations, and total budget estimates will now be calculated for {count} people.\n"
            f"• What would you like to explore next — attractions, daily itinerary, or travel dates?"
        )

    # ── 17. Default Context-Aware Response ──
    history_context = ""
    if history:
        last_reply = next((h.get("text", "") for h in reversed(history) if h.get("sender") == "assistant"), "")
        if last_reply and len(last_reply) > 20:
            history_context = f"\n\n*(Continuing our planning for {dest})*"

    return (
        f"I'm TripWise AI — your travel planning assistant for **{dest}** from **{start_loc}** "
        f"({travelers} traveller{'s' if travelers != 1 else ''}).{history_context}\n\n"
        f"**You can ask me about:**\n"
        f"• 📅 Day plans: *'What's the Day 3 plan?'*\n"
        f"• 🌤️ Weather: *'What's the weather like?'*\n"
        f"• 🚆 Transport: *'What transport options do I have?'*\n"
        f"• 💰 Budget: *'How can I cut costs?'*\n"
        f"• 🗺️ Proximity: *'Which attractions are close to each other?'*\n"
        f"• 🔄 Changes: *'Replace Day 2's afternoon activity'*\n"
        f"• 🍛 Food: *'Best food to try in {dest}?'*\n"
        f"• 📦 Packing: *'What should I pack?'*\n"
        f"• 📆 Timing: *'When is the best time to visit?'*\n"
        f"• 💱 Currency: *'What's the USD to INR rate?'*\n"
        f"• 🔍 Search: *'Opening hours and entry ticket prices?'*\n\n"
        f"What would you like to explore?"
    )
