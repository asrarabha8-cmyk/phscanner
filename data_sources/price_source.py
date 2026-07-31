"""
data_sources/price_source.py
-----------------------------
تنفيذ PriceDataSource باستخدام مكتبة yfinance (مجانية، بدون مفتاح API).
"""

import logging
from typing import Optional

import pandas as pd

from data_sources.base import PriceDataSource

logger = logging.getLogger(__name__)


class YFinancePriceSource(PriceDataSource):
    def get_history(self, ticker: str, period: str = "1y") -> Optional[pd.DataFrame]:
        try:
            import yfinance as yf

            df = yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=False)
            if df is None or df.empty:
                return None

            df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
            df.dropna(inplace=True)
            if len(df) < 15:
                # بيانات غير كافية لأي تحليل قاعدة موثوق
                return None
            return df
        except Exception as exc:  # noqa: BLE001
            logger.warning("فشل جلب بيانات السعر لـ %s: %s", ticker, exc)
            return None
