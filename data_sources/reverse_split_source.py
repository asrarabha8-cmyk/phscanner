"""
data_sources/reverse_split_source.py
--------------------------------------
يستخرج تاريخ آخر Reverse Split من Finnhub API (endpoint: /stock/split).

يستخدم rate limiter مشترك (finnhub_client.py) مع بقية مصادر Finnhub
لتفادي تجاوز حد 60 طلب/دقيقة الإجمالي لكل مفتاح API.

ملاحظة: Finnhub يرجع fromFactor و toFactor لكل split.
  fromFactor > toFactor  => Reverse Split (مثال: fromFactor=10, toFactor=1
                             يعني 1-for-10، أي ratio = toFactor/fromFactor = 0.1)
  fromFactor < toFactor  => Split عادي (تجزيء) -- لا يهمنا بهذا المشروع
"""

import logging
from datetime import date, timedelta
from typing import Optional

import requests

from data_sources.base import ReverseSplitSource
from data_sources.finnhub_client import FINNHUB_BASE_URL, get_api_key, throttle
from core.models import ReverseSplitInfo

logger = logging.getLogger(__name__)


class FinnhubReverseSplitSource(ReverseSplitSource):
    def __init__(self):
        self.api_key = get_api_key()

    def get_recent_reverse_splits(
        self, ticker: str, lookback_days: int, as_of: date
    ) -> Optional[ReverseSplitInfo]:
        throttle()
        try:
            start = as_of - timedelta(days=lookback_days)

            resp = requests.get(
                f"{FINNHUB_BASE_URL}/stock/split",
                params={
                    "symbol": ticker,
                    "from": start.isoformat(),
                    "to": as_of.isoformat(),
                    "token": self.api_key,
                },
                timeout=15,
            )
            resp.raise_for_status()
            splits = resp.json()

            if not splits:
                return None

            # نهتم فقط بالـ Reverse Split
            reverse_splits = [
                s for s in splits
                if s.get("fromFactor", 0) > s.get("toFactor", 0) and s.get("toFactor", 0) > 0
            ]
            if not reverse_splits:
                return None

            last = max(reverse_splits, key=lambda s: s["date"])
            ratio = last["toFactor"] / last["fromFactor"]
            split_date = date.fromisoformat(last["date"])

            return ReverseSplitInfo(split_date=split_date, ratio=ratio)

        except Exception as exc:  # noqa: BLE001
            logger.warning("فشل جلب بيانات Reverse Split (Finnhub) لـ %s: %s", ticker, exc)
            return None
