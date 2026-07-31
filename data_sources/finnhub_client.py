"""
data_sources/finnhub_client.py
---------------------------------
Rate limiter مشترك بين كل مصادر Finnhub (price, splits, الخ).
حد Finnhub المجاني هو 60 طلب/دقيقة لكل مفتاح API -- وهذا الحد
ينطبق على كل الـ endpoints مجتمعة، وليس لكل endpoint لحاله.
لذلك نحتاج throttling مشترك وthread-safe لأن الطلبات تصير بالتوازي
عبر ThreadPoolExecutor بـ screener.py.
"""

import threading
import time

import streamlit as st

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"

# أقل من 60 بهامش أمان يغطي كل المصادر مجتمعة
_MAX_CALLS_PER_MINUTE = 55
_MIN_INTERVAL_SECONDS = 60.0 / _MAX_CALLS_PER_MINUTE

_lock = threading.Lock()
_last_call_time = 0.0


def get_api_key() -> str:
    return st.secrets["FINNHUB_API_KEY"]


def throttle():
    """يضمن عدم تجاوز حد الطلبات بالدقيقة عبر كل الـ threads مجتمعة."""
    global _last_call_time
    with _lock:
        elapsed = time.time() - _last_call_time
        if elapsed < _MIN_INTERVAL_SECONDS:
            time.sleep(_MIN_INTERVAL_SECONDS - elapsed)
        _last_call_time = time.time()
