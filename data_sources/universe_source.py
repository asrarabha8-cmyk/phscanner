"""
data_sources/universe_source.py
---------------------------------
يجلب قائمة كل الرموز المتداولة على NASDAQ / NYSE / AMEX من ملفات
NASDAQ Trader الرسمية (مجانية، تُحدَّث يوميًا، بدون مفتاح API).

الملفان:
  nasdaqlisted.txt  -> أسهم NASDAQ فقط
  otherlisted.txt   -> أسهم NYSE و AMEX (وغيرها) - يوجد عمود "Exchange"
"""

import io
import logging
from typing import List

import requests

from config import NASDAQ_LISTED_URL, OTHER_LISTED_URL
from data_sources.base import UniverseSource

logger = logging.getLogger(__name__)

# رموز التبادل كما تظهر في عمود Exchange بملف otherlisted.txt
_OTHER_EXCHANGE_MAP = {
    "N": "NYSE",
    "A": "AMEX",
    "P": "NYSE",   # NYSE Arca -> نصنّفها كـ NYSE لغرض هذا المشروع
    "Z": "AMEX",
}


class NasdaqTraderUniverseSource(UniverseSource):
    def get_tickers(self, exchanges: List[str]) -> List[str]:
        tickers: List[str] = []

        if "NASDAQ" in exchanges:
            tickers.extend(self._fetch_nasdaq_listed())

        if "NYSE" in exchanges or "AMEX" in exchanges:
            tickers.extend(self._fetch_other_listed(exchanges))

        # إزالة التكرار والحفاظ على الترتيب
        seen = set()
        unique_tickers = []
        for t in tickers:
            if t not in seen:
                seen.add(t)
                unique_tickers.append(t)
        return unique_tickers

    def _fetch_nasdaq_listed(self) -> List[str]:
        try:
            text = requests.get(NASDAQ_LISTED_URL, timeout=20).text
            lines = text.strip().split("\n")
            header = lines[0].split("|")
            symbol_idx = header.index("Symbol")
            etf_idx = header.index("ETF") if "ETF" in header else None
            test_idx = header.index("Test Issue") if "Test Issue" in header else None

            result = []
            for line in lines[1:-1]:  # آخر سطر يحتوي على "File Creation Time"
                cols = line.split("|")
                if len(cols) <= symbol_idx:
                    continue
                if etf_idx is not None and cols[etf_idx] == "Y":
                    continue
                if test_idx is not None and cols[test_idx] == "Y":
                    continue
                symbol = cols[symbol_idx].strip()
                if symbol and "$" not in symbol:
                    result.append(symbol)
            return result
        except Exception as exc:  # noqa: BLE001
            logger.error("فشل جلب قائمة NASDAQ: %s", exc)
            return []

    def _fetch_other_listed(self, exchanges: List[str]) -> List[str]:
        try:
            text = requests.get(OTHER_LISTED_URL, timeout=20).text
            lines = text.strip().split("\n")
            header = lines[0].split("|")
            symbol_idx = header.index("ACT Symbol")
            exch_idx = header.index("Exchange")
            test_idx = header.index("Test Issue") if "Test Issue" in header else None
            etf_idx = header.index("ETF") if "ETF" in header else None

            result = []
            for line in lines[1:-1]:
                cols = line.split("|")
                if len(cols) <= max(symbol_idx, exch_idx):
                    continue
                exch_code = cols[exch_idx].strip()
                exch_name = _OTHER_EXCHANGE_MAP.get(exch_code)
                if exch_name is None or exch_name not in exchanges:
                    continue
                if test_idx is not None and cols[test_idx] == "Y":
                    continue
                if etf_idx is not None and cols[etf_idx] == "Y":
                    continue
                symbol = cols[symbol_idx].strip()
                if symbol and "$" not in symbol:
                    result.append(symbol)
            return result
        except Exception as exc:  # noqa: BLE001
            logger.error("فشل جلب قائمة NYSE/AMEX: %s", exc)
            return []
