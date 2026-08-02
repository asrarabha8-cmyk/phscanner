"""
data_sources/price_source.py
-----------------------------
تنفيذ PriceDataSource باستخدام Polygon.io API (اشتراك Stocks Starter:
طلبات غير محدودة، بيانات 5 سنين، Corporate Actions).

بما إنه الاشتراك غير محدود الطلبات، لا حاجة لـ throttling معقد هنا.
"""

import logging
from datetime import date, timedelta
from typing import Optional, Dict, List

import pandas as pd
import requests
import streamlit as st

from data_sources.base import PriceDataSource

logger = logging.getLogger(__name__)

POLYGON_BASE_URL = "https://api.polygon.io"


class PolygonPriceSource(PriceDataSource):
    def __init__(self):
        self.api_key = st.secrets["POLYGON_API_KEY"]

    def get_history(self, ticker: str, period: str = "1y") -> Optional[pd.DataFrame]:
        try:
            end = date.today()
            start = end - timedelta(days=400)  # هامش أمان فوق سنة

            resp = requests.get(
                f"{POLYGON_BASE_URL}/v2/aggs/ticker/{ticker}/range/1/day/"
                f"{start.isoformat()}/{end.isoformat()}",
                params={
                    "adjusted": "true",
                    "sort": "asc",
                    "limit": 500,
                    "apiKey": self.api_key,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            results = data.get("results")
            if not results:
                return None

            df = pd.DataFrame(results)
            df["datetime"] = pd.to_datetime(df["t"], unit="ms")
            df.set_index("datetime", inplace=True)

            df = df.rename(
                columns={
                    "o": "Open",
                    "h": "High",
                    "l": "Low",
                    "c": "Close",
                    "v": "Volume",
                }
            )
            df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
            df.dropna(inplace=True)
            if len(df) < 15:
                return None
            return df

        except Exception as exc:  # noqa: BLE001
            logger.warning("فشل جلب بيانات السعر (Polygon) لـ %s: %s", ticker, exc)
            return None

    def get_history_batch(
        self, tickers: List[str], period: str = "1y", batch_size: int = 100
    ) -> Dict[str, Optional[pd.DataFrame]]:
        """
        Polygon Starter لا يوفر bulk endpoint، لكن بما إنه الطلبات غير
        محدودة (Unlimited API Calls)، الطلب لكل سهم لحاله سريع وموثوق
        بدون throttling.
        """
        results: Dict[str, Optional[pd.DataFrame]] = {}
        for ticker in tickers:
            results[ticker] = self.get_history(ticker, period=period)
        return results
