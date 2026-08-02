"""
data_sources/reverse_split_source.py
--------------------------------------
يستخرج تاريخ آخر Reverse Split من Polygon.io API (endpoint:
/v3/reference/splits)، مع فلتر reverse_split=true مباشر من الـ API.

يعتمد على اشتراك Stocks Starter (طلبات غير محدودة)، فلا حاجة لـ throttling.
"""

import logging
from datetime import date, timedelta
from typing import Optional

import requests
import streamlit as st

from data_sources.base import ReverseSplitSource
from core.models import ReverseSplitInfo

logger = logging.getLogger(__name__)

POLYGON_SPLITS_URL = "https://api.polygon.io/v3/reference/splits"


class PolygonReverseSplitSource(ReverseSplitSource):
    def __init__(self):
        self.api_key = st.secrets["POLYGON_API_KEY"]

    def get_recent_reverse_splits(
        self, ticker: str, lookback_days: int, as_of: date
    ) -> Optional[ReverseSplitInfo]:
        try:
            start = as_of - timedelta(days=lookback_days)

            resp = requests.get(
                POLYGON_SPLITS_URL,
                params={
                    "ticker": ticker,
                    "reverse_split": "true",
                    "execution_date.gte": start.isoformat(),
                    "execution_date.lte": as_of.isoformat(),
                    "apiKey": self.api_key,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            results = data.get("results") or []
            if not results:
                return None

            latest = max(results, key=lambda r: r.get("execution_date", ""))

            split_from = float(latest.get("split_from", 0))
            split_to = float(latest.get("split_to", 0))
            if split_from <= 0 or split_to <= 0 or split_from <= split_to:
                return None

            ratio = split_to / split_from
            split_date = date.fromisoformat(latest["execution_date"])

            return ReverseSplitInfo(split_date=split_date, ratio=ratio)

        except Exception as exc:  # noqa: BLE001
            logger.warning("فشل جلب بيانات Reverse Split (Polygon) لـ %s: %s", ticker, exc)
            return None
