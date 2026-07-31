"""
data_sources/price_source.py
-----------------------------
تنفيذ PriceDataSource باستخدام Finnhub API (خطة مجانية، يحتاج مفتاح API
مخزّن بـ Streamlit secrets تحت اسم FINNHUB_API_KEY).

حد الخطة المجانية: 60 طلب/دقيقة (30 طلب/ثانية كحد أقصى لحظي).
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List

import pandas as pd
import requests
import streamlit as st

from data_sources.base import PriceDataSource

logger = logging.getLogger(__name__)

FINNHUB_CANDLE_URL = "https://finnhub.io/api/v1/stock/candle"

# حد آمن أقل من 60/دقيقة الرسمي، لتفادي الحافة تمامًا
_MAX_CALLS_PER_MINUTE = 55
_MIN_INTERVAL_SECONDS = 60.0 / _MAX_CALLS_PER_MINUTE


class FinnhubPriceSource(PriceDataSource):
    def __init__(self):
        self.api_key = st.secrets["FINNHUB_API_KEY"]
        self._last_call_time: float = 0.0

    def _throttle(self):
        """يضمن عدم تجاوز حد الطلبات بالدقيقة."""
        elapsed = time.time() - self._last_call_time
        if elapsed < _MIN_INTERVAL_SECONDS:
            time.sleep(_MIN_INTERVAL_SECONDS - elapsed)
        self._last_call_time = time.time()

    def get_history(self, ticker: str, period: str = "1y") -> Optional[pd.DataFrame]:
        self._throttle()
        try:
            end = datetime.now()
            start = end - timedelta(days=400)  # هامش أمان فوق سنة

            resp = requests.get(
                FINNHUB_CANDLE_URL,
                params={
                    "symbol": ticker,
                    "resolution": "D",
                    "from": int(start.timestamp()),
                    "to": int(end.timestamp()),
                    "token": self.api_key,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("s") != "ok":
                # "no_data" أو أي حالة غير ناجحة
                return None

            df = pd.DataFrame(
                {
                    "Open": data["o"],
                    "High": data["h"],
                    "Low": data["l"],
                    "Close": data["c"],
                    "Volume": data["v"],
                },
                index=pd.to_datetime(data["t"], unit="s"),
            )
            df.dropna(inplace=True)
            if len(df) < 15:
                return None
            return df

        except Exception as exc:  # noqa: BLE001
            logger.warning("فشل جلب بيانات السعر (Finnhub) لـ %s: %s", ticker, exc)
            return None

    def get_history_batch(
        self, tickers: List[str], period: str = "1y", batch_size: int = 100
    ) -> Dict[str, Optional[pd.DataFrame]]:
        """
        Finnhub ما عنده bulk endpoint حقيقي بالخطة المجانية، فنطلب سهم
        سهم مع throttling داخلي يحترم حد 60 طلب/دقيقة. batch_size هنا
        غير مستخدم فعليًا لكن موجود للتوافق مع الواجهة المستخدمة بـ screener.py.
        """
        results: Dict[str, Optional[pd.DataFrame]] = {}
        for ticker in tickers:
            results[ticker] = self.get_history(ticker, period=period)
        return results
