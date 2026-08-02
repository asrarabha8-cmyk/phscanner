"""
data_sources/price_source.py
-----------------------------
تنفيذ PriceDataSource باستخدام Twelve Data API مع batching حقيقي:
عدة رموز بطلب HTTP واحد (مفصولة بفاصلة)، ما يقلل عدد الطلبات الفعلية
بشكل كبير جدًا ويبقيها ضمن حد 8 طلبات/دقيقة، رغم إنه كل رمز لسا يستهلك
رصيد (credit) منفصل من حصة 800/يوم.
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

# أقل من 8/دقيقة بهامش أمان -- الحين نطبقها على "الطلبات" (batches)، مو الأسهم
_MAX_CALLS_PER_MINUTE = 7
_MIN_INTERVAL_SECONDS = 60.0 / _MAX_CALLS_PER_MINUTE

_lock = threading.Lock()
_last_call_time = 0.0

# عدد الرموز بكل طلب HTTP واحد -- هامش أمان تحت حد طول الـ URL
_SYMBOLS_PER_BATCH = 30


def _throttle():
    global _last_call_time
    with _lock:
        elapsed = time.time() - _last_call_time
        if elapsed < _MIN_INTERVAL_SECONDS:
            time.sleep(_MIN_INTERVAL_SECONDS - elapsed)
        _last_call_time = time.time()


def _parse_symbol_payload(symbol: str, payload: dict) -> Optional[pd.DataFrame]:
    if not isinstance(payload, dict) or payload.get("status") == "error":
        return None

    values = payload.get("values")
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
        if col not in df.columns:
            return None
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.dropna(inplace=True)
    if len(df) < 15:
        return None
    return df


class TwelveDataPriceSource(PriceDataSource):
    def __init__(self):
        self.api_key = st.secrets["TWELVEDATA_API_KEY"]

    def get_history(self, ticker: str, period: str = "1y") -> Optional[pd.DataFrame]:
        result = self.get_history_batch([ticker], period=period)
        return result.get(ticker)

    def get_history_batch(
        self, tickers: List[str], period: str = "1y", batch_size: int = None
    ) -> Dict[str, Optional[pd.DataFrame]]:
        """
        يجلب عدة رموز بطلب HTTP واحد لكل مجموعة (batch_size رمز)، ما يقلل
        عدد الطلبات الفعلية بشكل كبير مقارنة بطلب منفرد لكل سهم.
        """
        chunk_size = batch_size or _SYMBOLS_PER_BATCH
        results: Dict[str, Optional[pd.DataFrame]] = {}

        for i in range(0, len(tickers), chunk_size):
            chunk = tickers[i : i + chunk_size]
            _throttle()
            try:
                resp = requests.get(
                    f"{TWELVEDATA_BASE_URL}/time_series",
                    params={
                        "symbol": ",".join(chunk),
                        "interval": "1day",
                        "outputsize": 400,
                        "apikey": self.api_key,
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:  # noqa: BLE001
                logger.warning("فشل جلب دفعة الأسهم (Twelve Data) %s: %s", chunk, exc)
                for t in chunk:
                    results[t] = None
                continue

            if len(chunk) == 1:
                # عند رمز واحد فقط، الاستجابة كائن واحد بدون مفاتيح رموز
                results[chunk[0]] = _parse_symbol_payload(chunk[0], data)
            else:
                for ticker in chunk:
                    payload = data.get(ticker)
                    results[ticker] = _parse_symbol_payload(ticker, payload) if payload else None

        return results
