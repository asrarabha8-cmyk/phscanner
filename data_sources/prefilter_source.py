"""
data_sources/prefilter_source.py
-----------------------------------
ترشيح أولي سريع لكل الأسهم بالسعر والفوليوم، بطلب واحد فقط، قبل ما نروح
لمصدر البيانات العميق (Finnhub) للتحليل الكامل.

المصدر: NASDAQ Screener API (عام، بدون مفتاح).
ملاحظة: إذا فشل هذا المصدر أو رجع بيانات فاضية/غير متطابقة، نرجع القائمة
الكاملة كـ fallback آمن بدل ما نستبعد كل الأسهم بالغلط.
"""

import logging
from typing import List, Set

import requests

logger = logging.getLogger(__name__)

NASDAQ_SCREENER_URL = "https://api.nasdaq.com/api/screener/stocks"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.nasdaq.com/",
    "Origin": "https://www.nasdaq.com",
}


def get_prefiltered_tickers(
    all_tickers: List[str],
    max_price: float,
    min_dollar_volume: float,
    limit: int = 8000,
) -> List[str]:
    tickers_set: Set[str] = set(all_tickers)
    passed: List[str] = []

    try:
        resp = requests.get(
            NASDAQ_SCREENER_URL,
            headers=_HEADERS,
            params={"tableonly": "true", "limit": limit},
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        rows = payload.get("data", {}).get("table", {}).get("rows") or []
        logger.warning("الترشيح الأولي: تم جلب %d صف من NASDAQ", len(rows))
    except Exception as exc:  # noqa: BLE001
        logger.error("فشل جلب بيانات الترشيح الأولي من NASDAQ: %s", exc)
        return all_tickers

    if not rows:
        # رجعت بيانات فاضية (حظر صامت أو تغيير بالـ API) -- fallback آمن
        logger.warning("الترشيح الأولي: لا توجد صفوف، سيتم استخدام القائمة الكاملة")
        return all_tickers

    for row in rows:
        symbol = row.get("symbol", "").strip()
        if symbol not in tickers_set:
            continue
        try:
            price = float(row.get("lastsale", "0").replace("$", "").replace(",", ""))
            volume = float(row.get("volume", "0").replace(",", ""))
        except (ValueError, AttributeError):
            continue

        if price <= 0 or price > max_price:
            continue
        if price * volume < min_dollar_volume:
            continue
        passed.append(symbol)

    if not passed:
        # رجعت صفوف لكن التطابق فشل بالكامل (مثلاً اختلاف شكل الرموز) -- fallback آمن
        logger.warning(
            "الترشيح الأولي: 0 تطابق من أصل %d صف رغم النجاح -- استخدام القائمة الكاملة",
            len(rows),
        )
        return all_tickers

    logger.warning(
        "الترشيح الأولي: %d من أصل %d سهم اجتازوا فلتر السعر/الفوليوم",
        len(passed),
        len(all_tickers),
    )
    return passed
