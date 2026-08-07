"""
data_sources/shares_outstanding_source.py
--------------------------------------------
يجلب عدد الأسهم القائمة (Shares Outstanding) من Polygon.io لكل سهم.
يُستخدم لفلترة الأسهم ذات العدد المحدود (float منخفض)، التي تميل
للتحرك بعنف أكبر نسبيًا عند أي طلب شراء.
"""

import logging
from typing import Optional

import requests
import streamlit as st

logger = logging.getLogger(__name__)

POLYGON_BASE_URL = "https://api.polygon.io"


def get_shares_outstanding(ticker: str) -> Optional[float]:
    try:
        api_key = st.secrets["POLYGON_API_KEY"]
        resp = requests.get(
            f"{POLYGON_BASE_URL}/v3/reference/tickers/{ticker}",
            params={"apiKey": api_key},
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("results") or {}
        shares = results.get("share_class_shares_outstanding")
        return float(shares) if shares else None
    except Exception as exc:  # noqa: BLE001
        logger.debug("لا تتوفر بيانات عدد الأسهم القائمة لـ %s: %s", ticker, exc)
        return None
