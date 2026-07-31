"""
data_sources/price_source.py
-----------------------------
تنفيذ PriceDataSource باستخدام Twelve Data API (خطة مجانية، تحتاج مفتاح
API مخزّن بـ Streamlit secrets تحت اسم TWELVEDATA_API_KEY).

حدود الخطة المجانية: 8 طلبات/دقيقة و 800 طلب/يوم لكل مفتاح.
لهذا السبب الترشيح الأولي (تصغير عدد الأسهم قبل الوصول هنا) ضروري --
بدونه يستحيل تغطية آلاف الأسهم بحدود هذه الخطة.
"""

import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, List

import pandas as pd
import requests
import streamlit as st

from data_sources.base import PriceDataSource

logger = logging.getLogger(__name__)

TWELVEDATA_BASE_URL = "https://api.twelvedata.com"

# أقل من 8/دقيقة بهامش أمان
_MAX_CALLS_PER_MINUTE = 7
_MIN_INTERVAL_SECONDS = 60.0 / _MAX_CALLS_PER_MINUTE

_lock = threading.Lock()
_last_call_time = 0.0


def _throttle():
    """يضمن عدم تجاوز حد الطلبات بالدقيقة عبر كل الـ threads مجتمعة."""
    global _last_call_time
    with _lock:
        elapsed = time.time() - _last_call_time
        if elapsed < _MIN_INTERVAL_SECONDS:
            time.sleep(_MIN_INTERVAL_SECONDS - elapsed)
        _last_call_time = time.time()


class TwelveDataPriceSource(PriceDataSource):
    def __init__(self):
        self.api_key = st.secrets["TWELVEDATA_API_KEY"]

    def get_history(self, ticker: str, period: str = "1y") -> Optional[pd.DataFrame]:
        _throttle()
        try:
            resp = requests.get(
                f"{TWELVEDATA_BASE_URL}/time_series",
                params={
                    "symbol": ticker,
                    "interval": "1day",
                    "outputsize": 400,  # هامش أمان فوق سنة تداول
                    "apikey": self.api_key,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") == "error" or "values" not in data:
                logger.warning(
                    "فشل جلب بيانات السعر (Twelve Data) لـ %s: %s",
                    ticker,
                    data.get("message", "بدون تفاصيل"),
                )
                return None

            values = data["values"]
            if not values:
                return None

            df = pd.DataFrame(values)
            df["datetime"] = pd.to_datetime(df["datetime"])
            df.set_index("datetime", inplace=True)
            df.sort_index(inplace=True)  # Twelve Data يرجع الأحدث أولًا

            df = df.rename(
                columns={
                    "open": "Open",
                    "high": "High",
                    "low": "Low",
                    "close": "Close",
                    "volume": "Volume",
                }
            )
            for col in ["Open", "High", "Low", "Close", "Volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
            df.dropna(inplace=True)
            if len(df) < 15:
                return None
            return df

        except Exception as exc:  # noqa: BLE001
            logger.warning("فشل جلب بيانات السعر (Twelve Data) لـ %s: %s", ticker, exc)
            return None

    def get_history_batch(
        self, tickers: List[str], period: str = "1y", batch_size: int = 100
    ) -> Dict[str, Optional[pd.DataFrame]]:
        """
        Twelve Data المجاني ما فيه bulk endpoint حقيقي، فنطلب سهم سهم مع
        throttling يحترم حد 8 طلبات/دقيقة و800 طلب/يوم. batch_size هنا
        موجود فقط للتوافق مع الواجهة المستخدمة بـ screener.py.
        """
        results: Dict[str, Optional[pd.DataFrame]] = {}
        for ticker in tickers:
            results[ticker] = self.get_history(ticker, period=period)
        return results
