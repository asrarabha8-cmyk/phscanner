"""
data_sources/base.py
---------------------
كل مصادر البيانات في المشروع يجب أن تلتزم بهذه الواجهات المجردة.
الفائدة: طبقة التحليل (analysis) والمنسّق (screener) لا يعرفان أبدًا من أين
تأتي البيانات فعليًا (yfinance؟ API آخر؟ ملف محلي؟). هذا يسمح باستبدال أي
مصدر بيانات في المستقبل (مثلاً استبدال yfinance بـ Polygon.io) دون تعديل
أي سطر في باقي المشروع.
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import List, Optional

import pandas as pd

from core.models import NewsCheckResult, ReverseSplitInfo, ShortInterestInfo


class PriceDataSource(ABC):
    @abstractmethod
    def get_history(self, ticker: str, period: str = "1y") -> Optional[pd.DataFrame]:
        """
        يرجع DataFrame يحتوي على أعمدة:
        Open, High, Low, Close, Volume — مفهرسة بالتاريخ (index = DatetimeIndex).
        يرجع None إذا تعذر جلب البيانات.
        """
        raise NotImplementedError


class UniverseSource(ABC):
    @abstractmethod
    def get_tickers(self, exchanges: List[str]) -> List[str]:
        """يرجع قائمة رموز الأسهم العادية (يستبعد ETFs وصناديق الاختبار)."""
        raise NotImplementedError


class ReverseSplitSource(ABC):
    @abstractmethod
    def get_recent_reverse_splits(
        self, ticker: str, lookback_days: int, as_of: date
    ) -> Optional[ReverseSplitInfo]:
        """يرجع معلومات آخر Reverse Split ضمن النطاق الزمني، أو None إن لم يوجد."""
        raise NotImplementedError


class NewsSource(ABC):
    @abstractmethod
    def check_impactful_news(
        self, ticker: str, lookback_days: int
    ) -> NewsCheckResult:
        raise NotImplementedError


class ShortInterestSource(ABC):
    @abstractmethod
    def get_short_interest(self, ticker: str) -> ShortInterestInfo:
        """
        يرجع ShortInterestInfo(available=False) إذا لم يكن المصدر مهيّأ
        (مثلاً بدون مفتاح API) بدل أن يفشل السكرينر بالكامل.
        """
        raise NotImplementedError
