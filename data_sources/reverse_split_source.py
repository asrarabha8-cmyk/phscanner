"""
data_sources/reverse_split_source.py
--------------------------------------
يستخرج تاريخ آخر Reverse Split من بيانات yfinance (Ticker.splits).

ملاحظة مهمة: yfinance يعطي "split ratio" حيث:
  ratio > 1  => Split عادي (تجزيء) — مثال 2.0 يعني 2-for-1
  ratio < 1  => Reverse Split — مثال 0.1 يعني 1-for-10
هذا المشروع يهتم فقط بالحالة الثانية (ratio < 1).
"""

import logging
from datetime import date, timedelta
from typing import Optional

from data_sources.base import ReverseSplitSource
from core.models import ReverseSplitInfo

logger = logging.getLogger(__name__)


class YFinanceReverseSplitSource(ReverseSplitSource):
    def get_recent_reverse_splits(
        self, ticker: str, lookback_days: int, as_of: date
    ) -> Optional[ReverseSplitInfo]:
        try:
            import yfinance as yf

            splits = yf.Ticker(ticker).splits
            if splits is None or splits.empty:
                return None

            cutoff = as_of - timedelta(days=lookback_days)
            reverse_splits = splits[splits < 1.0]
            if reverse_splits.empty:
                return None

            # آخر Reverse Split زمنيًا
            last_date = reverse_splits.index[-1].date()
            if last_date < cutoff:
                return None

            ratio = float(reverse_splits.iloc[-1])
            return ReverseSplitInfo(split_date=last_date, ratio=ratio)
        except Exception as exc:  # noqa: BLE001
            logger.warning("فشل جلب بيانات Reverse Split لـ %s: %s", ticker, exc)
            return None
