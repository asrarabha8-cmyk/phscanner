"""
data_sources/reverse_split_source.py
--------------------------------------
يستخرج تاريخ آخر Reverse Split من Twelve Data API (endpoint: /splits).

يستخدم نفس throttling الخاص بـ price_source.py (8 طلبات/دقيقة، 800/يوم)
لأن الاثنين يستهلكان من نفس حصة المفتاح.

ملاحظة: Twelve Data يرجع split_from و split_to لكل حدث تقسيم.
  split_from > split_to  => Reverse Split (مثال: split_from=10, split_to=1
                             يعني 1-for-10، أي ratio = split_to/split_from = 0.1)
  split_from < split_to  => Split عادي (تجزيء) -- لا يهمنا بهذا المشروع
"""

import logging
import time
import threading
from datetime import date, timedelta
from typing import Optional

import requests
import streamlit as st

from data_sources.base import ReverseSplitSource
from core.models import ReverseSplitInfo

logger = logging.getLogger(__name__)

TWELVEDATA_BASE_URL = "https://api.twelvedata.com"

# نفس حد price_source.py -- الاثنين يشاركان نفس مفتاح API ونفس الحصة اليومية
_MAX_CALLS_PER_MINUTE = 7
_MIN_INTERVAL_SECONDS = 60.0 / _MAX_CALLS_PER_MINUTE

_lock = threading.Lock()
_last_call_time = 0.0


def _throttle():
    global _last_call_time
    with _lock:
        elapsed = time.time() - _last_call_time
        if elapsed < _MIN_INTERVAL_SECONDS:
            time.sleep(_MIN_INTERVAL_SECONDS - elapsed)
        _last_call_time = time.time()


class TwelveDataReverseSplitSource(ReverseSplitSource):
    def __init__(self):
        self.api_key = st.secrets["TWELVEDATA_API_KEY"]

    def get_recent_reverse_splits(
        self, ticker: str, lookback_days: int, as_of: date
    ) -> Optional[ReverseSplitInfo]:
        _throttle()
        try:
            start = as_of - timedelta(days=lookback_days)

            resp = requests.get(
                f"{TWELVEDATA_BASE_URL}/splits",
                params={
                    "symbol": ticker,
                    "start_date": start.isoformat(),
                    "end_date": as_of.isoformat(),
                    "apikey": self.api_key,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") == "error":
                logger.warning(
                    "فشل جلب بيانات Reverse Split (Twelve Data) لـ %s: %s",
                    ticker,
                    data.get("message", "بدون تفاصيل"),
                )
                return None

            splits = data.get("splits") or data.get("data") or []
            if not splits:
                return None

            reverse_splits = []
            for s in splits:
                try:
                    split_from = float(s.get("split_from", 0))
                    split_to = float(s.get("split_to", 0))
                except (ValueError, TypeError):
                    continue
                if split_from > split_to > 0:
                    reverse_splits.append((s.get("date"), split_from, split_to))

            if not reverse_splits:
                return None

            last_date_str, split_from, split_to = max(reverse_splits, key=lambda x: x[0])
            ratio = split_to / split_from
            split_date = date.fromisoformat(last_date_str)

            return ReverseSplitInfo(split_date=split_date, ratio=ratio)

        except Exception as exc:  # noqa: BLE001
            logger.warning("فشل جلب بيانات Reverse Split (Twelve Data) لـ %s: %s", ticker, exc)
            return None
