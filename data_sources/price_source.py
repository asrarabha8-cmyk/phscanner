"""
data_sources/price_source.py
-----------------------------
تنفيذ PriceDataSource باستخدام Finnhub API (خطة مجانية، يحتاج مفتاح API
مخزّن بـ Streamlit secrets تحت اسم FINNHUB_API_KEY).

يستخدم rate limiter مشترك (finnhub_client.py) مع بقية مصادر Finnhub
لتفادي تجاوز حد 60 طلب/دقيقة الإجمالي لكل مفتاح API.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List

import pandas as pd
import requests

from data_sources.base import PriceDataSource
from data_sources.finnhub_client import FINNHUB_BASE_URL, get_api_key, throttle

logger = logging.getLogger(__name__)


class FinnhubPriceSource(PriceDataSource):
    def __init__(self):
        self.api_key = get_api_key()

    def get_history(self, ticker: str, period: str = "1y") -> Optional[pd.DataFrame]:
        throttle()
        try:
            end = datetime.now()
            start = end - timedelta(days=400)  # هامش أمان فوق سنة

            resp = requests.get(
                f"{FINNHUB_BASE_URL}/stock/candle",
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
        سهم مع throttling مشترك يحترم حد 60 طلب/دقيقة الإجمالي.
        batch_size موجود هنا فقط للتوافق مع الواجهة المستخدمة بـ
        screener.py -- غير مستخدم فعليًا بهذا التنفيذ.
        """
        results: Dict[str, Optional[pd.DataFrame]] = {}
        for ticker in tickers:
            results[ticker] = self.get_history(ticker, period=period)
        return results
