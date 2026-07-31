"""
data_sources/prefilter_source.py
-----------------------------------
ترشيح أولي سريع لكل الأسهم بالسعر والفوليوم، بطلب واحد فقط، قبل ما نروح
لـ yfinance للتحليل العميق. يقلل عدد الأسهم من ~7000 إلى مجموعة أصغر
بكثير، وبالتالي يقلل الضغط الفعلي على yfinance ويتفادى rate limiting.

المصدر: NASDAQ Screener API (عام، بدون مفتاح، يرجع كل السوق بطلب واحد).
"""

import logging
from typing import List, Set

import requests

logger = logging.getLogger(__name__)

NASDAQ_SCREENER_URL = "https://api.nasdaq.com/api/screener/stocks"

_HEADERS = {
    # nasdaq.com يرفض الطلبات بدون user-agent شبيه بالمتصفح
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def get_prefiltered_tickers(
    all_tickers: List[str],
    max_price: float,
    min_dollar_volume: float,
    limit: int = 8000,
) -> List[str]:
    """
    يرجع فقط الرموز اللي سعرها وفوليومها يحققان الشروط الأساسية،
    بناءً على بيانات NASDAQ Screener (مو yfinance).
    """
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
        rows = resp.json()["data"]["table"]["rows"]
    except Exception as exc:  # noqa: BLE001
        logger.error("فشل جلب بيانات الترشيح الأولي من NASDAQ: %s", exc)
        # في حال فشل الترشيح الأولي، نرجع القائمة الكاملة كما هي
        # (fallback آمن -- ما نخسر أي سهم، بس نرجع للوضع البطيء)
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

    logger.warning(
        "الترشيح الأولي: %d من أصل %d سهم اجتازوا فلتر السعر/الفوليوم",
        len(passed),
        len(all_tickers),
    )
    return passed
