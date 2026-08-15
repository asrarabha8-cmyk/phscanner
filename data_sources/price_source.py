"""
data_sources/price_source.py
-----------------------------
تنفيذ PriceDataSource باستخدام Polygon.io API.

مهم: بدل الاعتماد على الشمعة اليومية الجاهزة من Polygon (اللي تشمل
Pre-market وAfter-hours)، نبني الشمعة اليومية بأنفسنا من بيانات كل دقيقة
(Minute Aggregates)، مع تصفية أي دقيقة تقع خارج وقت السوق الرسمي
(9:30 صباحًا - 4:00 مساءً بتوقيت شرق أمريكا). هذا يطابق منهجية معلمك:
"الفريم اليومي فقط وقت الماركت".

ملاحظة أداء: هذا أبطأ بكثير من الشمعة اليومية الجاهزة، لأن حجم البيانات
المطلوب لكل سهم أكبر بمئات المرات (آلاف نقاط بالدقيقة بدل نقطة باليوم).
"""

import logging
from datetime import date, datetime, time as dtime, timedelta
from typing import Optional, Dict, List
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

from data_sources.base import PriceDataSource

logger = logging.getLogger(__name__)

POLYGON_BASE_URL = "https://api.polygon.io"
_ET = ZoneInfo("America/New_York")
_MARKET_OPEN = dtime(9, 30)
_MARKET_CLOSE = dtime(16, 0)


class PolygonPriceSource(PriceDataSource):
    def __init__(self):
        self.api_key = st.secrets["POLYGON_API_KEY"]

    def get_history(self, ticker: str, period: str = "1y") -> Optional[pd.DataFrame]:
        try:
            end = date.today()
            start = end - timedelta(days=400)

            minute_df = self._fetch_minute_bars(ticker, start, end)
            if minute_df is None or minute_df.empty:
                return None

            daily_df = self._build_regular_hours_daily(minute_df)
            if daily_df is None or len(daily_df) < 15:
                return None
            return daily_df

        except Exception as exc:  # noqa: BLE001
            logger.warning("فشل بناء بيانات السعر (Polygon minute) لـ %s: %s", ticker, exc)
            return None

    # ------------------------------------------------------------------
    def _fetch_minute_bars(self, ticker: str, start: date, end: date) -> Optional[pd.DataFrame]:
        """يجلب كل بيانات الدقائق ضمن المدى، مع تصفح الصفحات (pagination)."""
        all_results: List[dict] = []

        url = (
            f"{POLYGON_BASE_URL}/v2/aggs/ticker/{ticker}/range/1/minute/"
            f"{start.isoformat()}/{end.isoformat()}"
        )
        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000,
            "apiKey": self.api_key,
        }

        while url:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            results = data.get("results") or []
            all_results.extend(results)

            next_url = data.get("next_url")
            if next_url:
                url = next_url
                params = {"apiKey": self.api_key}  # next_url يحتاج المفتاح فقط
            else:
                url = None

        if not all_results:
            return None

        df = pd.DataFrame(all_results)
        df["datetime_utc"] = pd.to_datetime(df["t"], unit="ms", utc=True)
        df.set_index("datetime_utc", inplace=True)
        df = df.rename(columns={"o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume"})
        return df[["Open", "High", "Low", "Close", "Volume"]]

    # ------------------------------------------------------------------
    def _build_regular_hours_daily(self, minute_df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """يصفّي وقت السوق الرسمي فقط، ويجمع كل يوم لشمعة يومية واحدة."""
        et_index = minute_df.index.tz_convert(_ET)
        times = et_index.time
        mask = (times >= _MARKET_OPEN) & (times < _MARKET_CLOSE)

        regular = minute_df[mask].copy()
        if regular.empty:
            return None

        regular["trading_date"] = et_index[mask].date

        daily = regular.groupby("trading_date").agg(
            Open=("Open", "first"),
            High=("High", "max"),
            Low=("Low", "min"),
            Close=("Close", "last"),
            Volume=("Volume", "sum"),
        )
        daily.index = pd.to_datetime(daily.index)
        daily.sort_index(inplace=True)
        daily.dropna(inplace=True)
        return daily

    # ------------------------------------------------------------------
    def get_history_batch(
        self, tickers: List[str], period: str = "1y", batch_size: int = 100
    ) -> Dict[str, Optional[pd.DataFrame]]:
        """
        لا يوجد bulk endpoint حقيقي لهذا الأسلوب. كل سهم يحتاج طلب/طلبات
        منفصلة (بسبب حجم بيانات الدقائق وimperative التصفح بالصفحات).
        """
        results: Dict[str, Optional[pd.DataFrame]] = {}
        for ticker in tickers:
            results[ticker] = self.get_history(ticker, period=period)
        return results
