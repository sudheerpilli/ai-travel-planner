"""
Free Web Search Service for TripWise — powered by DuckDuckGo (no API key required).
Provides real-time travel information: attraction opening hours, entry prices,
travel advisories, visa requirements, and recent news about destinations.
"""

from __future__ import annotations
import hashlib
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# In-memory cache: key -> (timestamp, result)
_SEARCH_CACHE: dict[str, tuple[float, list[dict]]] = {}
_CACHE_TTL_SECONDS = 1800  # 30 minutes

# Rate-limit guard: last search timestamp
_LAST_SEARCH_TIME: float = 0.0
_MIN_SEARCH_INTERVAL = 1.5  # seconds between searches to be polite


def _cache_key(query: str) -> str:
    return hashlib.sha256(query.lower().strip().encode()).hexdigest()[:16]


def _is_cached(key: str) -> bool:
    if key not in _SEARCH_CACHE:
        return False
    ts, _ = _SEARCH_CACHE[key]
    return (time.time() - ts) < _CACHE_TTL_SECONDS


def web_search(
    query: str,
    max_results: int = 5,
    safesearch: str = "moderate"
) -> list[dict]:
    """
    Search DuckDuckGo and return a list of result dicts:
        {"title": str, "url": str, "snippet": str}

    Returns an empty list on failure rather than raising.
    Results are cached for 30 minutes to avoid hammering DDG.
    """
    global _LAST_SEARCH_TIME

    key = _cache_key(query)
    if _is_cached(key):
        logger.debug("Search cache hit for: %s", query[:60])
        _, results = _SEARCH_CACHE[key]
        return results

    # Polite rate limiting
    elapsed = time.time() - _LAST_SEARCH_TIME
    if elapsed < _MIN_SEARCH_INTERVAL:
        time.sleep(_MIN_SEARCH_INTERVAL - elapsed)

    try:
        # Support both 'ddgs' and legacy 'duckduckgo_search' packages
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results, safesearch=safesearch):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", r.get("url", "")),
                    "snippet": r.get("body", r.get("snippet", ""))
                })
        _LAST_SEARCH_TIME = time.time()
        _SEARCH_CACHE[key] = (time.time(), results)
        logger.info("Web search returned %d results for: %s", len(results), query[:60])
        return results

    except ImportError:
        logger.warning("Neither ddgs nor duckduckgo_search is installed. Run: pip install duckduckgo-search")
        return []
    except Exception as exc:
        logger.warning("Web search failed for '%s': %s", query[:60], exc)
        _LAST_SEARCH_TIME = time.time()
        return []


def search_attraction_info(attraction_name: str, destination: str) -> str:
    """
    Search for opening hours, entry fees, and practical info for a specific attraction.
    Returns a formatted summary string; empty string on failure.
    """
    query = f"{attraction_name} {destination} opening hours entry fee 2024 2025"
    results = web_search(query, max_results=4)
    if not results:
        return ""
    useful = [r for r in results if len(r.get("snippet", "")) > 40][:2]
    if not useful:
        return ""
    parts = []
    for r in useful:
        parts.append(f"• {r['snippet'][:200]}  [Source: {r['url']}]")
    return "\n".join(parts)


def search_destination_news(destination: str) -> list[dict]:
    """
    Returns recent travel news / advisories for a destination.
    """
    query = f"{destination} travel news tourism 2025"
    return web_search(query, max_results=4)


def search_visa_requirements(destination: str, nationality: str = "Indian") -> list[dict]:
    """
    Returns visa requirement info for a destination.
    """
    query = f"{nationality} passport visa {destination} requirements 2025"
    return web_search(query, max_results=4)


def search_travel_tips(destination: str) -> list[dict]:
    """
    Returns traveller tips and practical advice for a destination.
    """
    query = f"travel tips {destination} tourist guide what to know 2025"
    return web_search(query, max_results=4)


def format_search_results_as_context(results: list[dict], max_chars: int = 800) -> str:
    """
    Formats search results into a compact context block for LLM injection.
    """
    if not results:
        return ""
    lines = ["[WEB SEARCH RESULTS]"]
    total = 0
    for i, r in enumerate(results, 1):
        snippet = r.get("snippet", "")[:200]
        url = r.get("url", "")
        title = r.get("title", "")
        entry = f"{i}. {title}: {snippet} ({url})"
        if total + len(entry) > max_chars:
            break
        lines.append(entry)
        total += len(entry)
    lines.append("[END SEARCH RESULTS]")
    return "\n".join(lines)


def should_web_search(query: str) -> bool:
    """
    Heuristic: returns True if the question likely benefits from a live web search.
    Avoids searching for simple greetings, day recalls, or budget math.
    """
    q = query.lower()

    # Never search for these
    skip_keywords = [
        "hello", "hi ", "hey ", "good morning", "good evening",
        "day 1", "day 2", "day 3", "day 4", "day 5",
        "how much", "total cost", "my budget", "breakdown",
        "what is my", "in my trip", "my itinerary",
        "pack", "luggage", "suitcase",
    ]
    if any(k in q for k in skip_keywords):
        return False

    # Strongly search for these
    search_keywords = [
        "open", "hours", "entry fee", "ticket price", "how to reach",
        "current", "latest", "recent", "news", "2024", "2025", "2026",
        "visa", "passport", "restriction",
        "flight price", "train ticket", "bus fare",
        "hotel near", "best restaurant", "must eat",
        "is it safe", "safety", "crime", "tips for",
        "festival", "event", "celebration",
        "currency", "exchange rate",
    ]
    return any(k in q for k in search_keywords)
