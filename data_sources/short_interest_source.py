"""
data_sources/short_interest_source.py
----------------------------------------
يستخدم Polygon.io لجلب بيانات Short Interest.
Borrow Fee يُجلب من iBorrowDesk (endpoint غير رسمي، بدون توثيق عام) --
تشخيص مؤقت مضاف للتأكد من شكل الاستجابة الفعلي.
"""

import logging

import requests
import streamlit as st

from config import IBORROWDESK_BASE_URL
from core.models import ShortInterestInfo
from data_sources.base import ShortInterestSource

logger = logging.getLogger(__name__)

POLYGON_BASE_URL = "https://api.polygon.io"

_logged_borrow_sample = False


class CompositeShortInterestSource(ShortInterestSource):
    def __init__(self):
        self.api_key = st.secrets["POLYGON_API_KEY"]

    def get_short_interest(self, ticker: str) -> ShortInterestInfo:
        borrow_fee = self._get_borrow_fee(ticker)
        short_float = self._get_short_float_pct(ticker)

        available = borrow_fee is not None or short_float is not None
        return ShortInterestInfo(
            short_float_pct=short_float,
            borrow_fee_pct=borrow_fee,
            available=available,
        )

    def _get_short_float_pct(self, ticker: str):
        try:
            resp = requests.get(
                f"{POLYGON_BASE_URL}/stocks/v1/short-interest",
                params={
                    "ticker": ticker,
                    "limit": 1,
                    "sort": "settlement_date.desc",
                    "apiKey": self.api_key,
                },
                timeout=15,
            )
            resp.raise_for_status()
            results = resp.json().get("results") or []
            if not results:
                return None

            short_shares = float(results[0].get("short_interest") or 0)
            if short_shares <= 0:
                return None

            resp2 = requests.get(
                f"{POLYGON_BASE_URL}/v3/reference/tickers/{ticker}",
                params={"apiKey": self.api_key},
                timeout=15,
            )
            resp2.raise_for_status()
            ticker_info = resp2.json().get("results") or {}
            shares_outstanding = float(ticker_info.get("share_class_shares_outstanding") or 0)

            if shares_outstanding <= 0 or short_shares <= 0:
                return None

            pct = (short_shares / shares_outstanding) * 100
            if pct <= 0:
                return None

            return round(pct, 2)

        except Exception as exc:  # noqa: BLE001
            logger.debug("لا تتوفر بيانات Short Interest (Polygon) لـ %s: %s", ticker, exc)
            return None

    def _get_borrow_fee(self, ticker: str):
        global _logged_borrow_sample
        try:
            resp = requests.get(f"{IBORROWDESK_BASE_URL}/{ticker}", timeout=10)

            if not _logged_borrow_sample:
                logger.warning(
                    "تشخيص Borrow Fee: URL=%s status=%d رد أول 300 حرف: %s",
                    f"{IBORROWDESK_BASE_URL}/{ticker}",
                    resp.status_code,
                    resp.text[:300],
                )
                _logged_borrow_sample = True

            if resp.status_code != 200:
                return None
            data = resp.json()
            daily = data.get("daily")
            if not daily:
                return None
            latest = daily[-1]
            return float(latest.get("fee"))
        except Exception as exc:  # noqa: BLE001
            logger.debug("لا تتوفر بيانات Borrow Fee لـ %s: %s", ticker, exc)
            return None
