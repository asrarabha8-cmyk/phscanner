"""
data_sources/split_calendar_source.py
----------------------------------------
يجلب تقويم Reverse Splits مباشرة من NASDAQ (endpoint: /api/calendar/splits)
لكل يوم ضمن فترة البحث، بدل ما نفحص كل سهم لحاله. هذا يقلل العدد النهائي
من مئات الأسهم إلى فقط الأسهم اللي فعلاً عملت Reverse Split بالفترة --
عادة عدد صغير جدًا (عشرات كحد أقصى).

ملاحظة: شكل استجابة NASDAQ غير مؤكد 100% بدون اختبار فعلي، لذلك الكود
يطبع تشخيصًا (أول سجل خام) لأول يوم ناجح، لنتأكد من أسماء الحقول الصحيحة.
"""

import logging
from datetime import date, timedelta
from typing import Dict, Optional

import requests

from core.models import ReverseSplitInfo

logger = logging.getLogger(__name__)

NASDAQ_SPLITS_CALENDAR_URL = "https://api.nasdaq.com/api/calendar/splits"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.nasdaq.com/",
    "Origin": "https://www.nasdaq.com",
}

_logged_sample = False


def get_recent_reverse_splits_calendar(
    lookback_days: int, as_of: date
) -> Dict[str, ReverseSplitInfo]:
    global _logged_sample
    results: Dict[str, ReverseSplitInfo] = {}

    for i in range(lookback_days + 1):
        day = as_of - timedelta(days=i)
        try:
            resp = requests.get(
                NASDAQ_SPLITS_CALENDAR_URL,
                headers=_HEADERS,
                params={"date": day.isoformat()},
                timeout=15,
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("فشل جلب تقويم splits لتاريخ %s: %s", day, exc)
            continue

        rows = (
            payload.get("data", {}).get("calendar", {}).get("rows")
            if payload.get("data")
            else None
        ) or []

        if rows and not _logged_sample:
            logger.warning("تقويم Splits: عينة أول سجل = %s", rows[0])
            _logged_sample = True

        for row in rows:
            symbol = (row.get("symbol") or "").strip().upper()
            ratio_str = row.get("ratio") or ""
            if not symbol or ":" not in ratio_str:
                continue
            try:
                parts = [p.strip() for p in ratio_str.split(":")]
                new_shares = float(parts[0])
                old_shares = float(parts[1])
            except (ValueError, IndexError):
                continue

            if old_shares <= 0 or new_shares <= 0:
                continue

            # Reverse Split: old_shares > new_shares (مثال 1:10 -> 1 جديد مقابل 10 قديم)
            if old_shares <= new_shares:
                continue  # هذا split عادي (تجزيء)، مو reverse

            ratio = new_shares / old_shares
            results[symbol] = ReverseSplitInfo(split_date=day, ratio=ratio)

    logger.warning(
        "تقويم Splits: %d سهم عندهم Reverse Split خلال %d يوم",
        len(results),
        lookback_days,
    )
    return results
