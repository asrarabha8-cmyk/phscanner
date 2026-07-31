"""
data_sources/prefilter_source.py
-----------------------------------
ترشيح أولي سريع لكل الأسهم بالسعر فقط، بطلب واحد، قبل ما نروح لمصدر
البيانات العميق (Twelve Data) للتحليل الكامل.

المصدر: NASDAQ Screener API (عام، بدون مفتاح).
ملاحظة: NASDAQ Screener لا يرجع عمود الفوليوم بشكل موثوق مع هذا الشكل
من الطلب، لذلك نكتفي هنا بفلترة السعر فقط. فلتر الفوليوم (min_dollar_volume)
يبقى مطبّقًا لاحقًا بمرحلة التحليل العميق في screener.py، فلا نخسر الدقة.
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
    min_price: float = 1.0,
    limit: int = 8000,
) -> List[str]:
    tickers_set: Set[str] = {t.strip().upper() for t in all_tickers}
    passed: List[str] = []

    try:
        resp = requests.get(
            NASDAQ_SCREENER_URL,
            headers=_HEADERS,
            params={"tableonly": "true", "limit": limit},
            timeout=30,
        )
        logger.warning("الترشيح الأولي: NASDAQ رجع status_code=%d", resp.status_code)
        resp.raise_for_status()
        payload = resp.json()
        rows = payload.get("data", {}).get("table", {}).get("rows") or []
        logger.warning("الترشيح الأولي: تم جلب %d صف من NASDAQ", len(rows))
    except Exception as exc:  # noqa: BLE001
        logger.error("فشل جلب بيانات الترشيح الأولي من NASDAQ: %s", exc)
        return all_tickers

    if not rows:
        logger.warning("الترشيح الأولي: لا توجد صفوف، استخدام القائمة الكاملة")
        return all_tickers

    matched_symbols = 0
    for row in rows:
        symbol = row.get("symbol", "").strip().upper()
        if symbol not in tickers_set:
            continue
        matched_symbols += 1
        try:
            price = float(row.get("lastsale", "0").replace("$", "").replace(",", ""))
        except (ValueError, AttributeError):
            continue

        if price < min_price or price > max_price:
            continue
        passed.append(symbol)

    logger.warning(
        "الترشيح الأولي: %d صف تطابقت رموزهم من أصل %d صف",
        matched_symbols,
        len(rows),
    )

    if not passed:
        logger.warning(
            "الترشيح الأولي: 0 اجتاز فلتر السعر رغم %d تطابق -- استخدام القائمة الكاملة",
            matched_symbols,
        )
        return all_tickers

    logger.warning(
        "الترشيح الأولي: %d من أصل %d سهم اجتازوا فلتر السعر",
        len(passed),
        len(all_tickers),
    )
    return passed
