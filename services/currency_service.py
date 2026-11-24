"""
Currency service for TripWise.
Maintains consistent internal calculation currency (INR) and provides conversion to USD, EUR, GBP.
"""

from __future__ import annotations
import time
import requests

CURRENCY_SYMBOLS = {
    "INR": "₹",
    "USD": "$",
    "EUR": "€",
    "GBP": "£"
}

FALLBACK_RATES_FROM_INR = {
    "INR": 1.0,
    "USD": 0.012,
    "EUR": 0.011,
    "GBP": 0.0095
}

_rate_cache: dict[str, tuple[float, float]] = {}
CACHE_TTL = 3600  # 1 hour


def get_exchange_rate(currency: str) -> tuple[float, str]:
    """
    Returns (rate_from_inr, note).
    e.g. 1 INR -> rate USD
    """
    currency = (currency or "INR").strip().upper()
    if currency == "INR":
        return 1.0, "No conversion needed (INR)"

    now = time.time()
    if currency in _rate_cache:
        cached_rate, timestamp = _rate_cache[currency]
        if now - timestamp < CACHE_TTL:
            return cached_rate, "Live exchange rate (cached)"

    try:
        resp = requests.get(
            "https://open.er-api.com/v6/latest/INR",
            timeout=2,
            headers={"User-Agent": "TripWisePlanner/2.0"}
        )
        if resp.status_code == 200:
            data = resp.json()
            rates = data.get("rates", {})
            if currency in rates:
                rate = float(rates[currency])
                _rate_cache[currency] = (rate, now)
                return rate, "Live exchange rate"
    except Exception:
        pass

    rate = FALLBACK_RATES_FROM_INR.get(currency, 1.0)
    return rate, "Standard estimated exchange rate"


def convert_from_inr(amount_inr: float, currency: str) -> float:
    rate, _ = get_exchange_rate(currency)
    return round(amount_inr * rate, 2)


def convert_to_inr(amount_foreign: float, currency: str) -> float:
    rate, _ = get_exchange_rate(currency)
    if rate <= 0:
        return amount_foreign
    return round(amount_foreign / rate, 2)


def format_money(amount: float, currency: str) -> str:
    sym = CURRENCY_SYMBOLS.get(currency.upper(), currency.upper() + " ")
    return f"{sym}{amount:,.0f}" if amount >= 10 else f"{sym}{amount:,.2f}"
