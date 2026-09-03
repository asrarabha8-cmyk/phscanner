"""
config.py
---------
نقطة تجميع كل الإعدادات والقيم الافتراضية لمشروع Phoenix Scanner.
أي تعديل على الحدود أو الأوزان يجب أن يمر من هنا فقط، ولا يجب أن يتكرر
تعريف أي رقم "سحري" (magic number) داخل الطبقات الأخرى.
"""

from dataclasses import dataclass, field
from typing import List


TARGET_EXCHANGES: List[str] = ["NYSE", "NASDAQ", "AMEX"]

NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"


REVERSE_SPLIT_LOOKBACK_OPTIONS = [30, 60, 90, 180]
DEFAULT_REVERSE_SPLIT_LOOKBACK = 90

SHORT_FLOAT_OPTIONS = [15, 20, 25]
DEFAULT_SHORT_FLOAT_MIN = 15

TOUCHES_OPTIONS = [2, 3, 4, 5]
DEFAULT_MIN_TOUCHES = 2

# تم التعديل لمطابقة كلام المعلم بالضبط: "ثبات فوق الدعم 4 جلسات"
BASE_DAYS_OPTIONS = [4, 7, 10, 20, 40, 60]
DEFAULT_MIN_BASE_DAYS = 4

DISTANCE_FROM_SUPPORT_OPTIONS = [2, 3, 5]
DEFAULT_MAX_DISTANCE_FROM_SUPPORT = 5.0

DEFAULT_SUPPORT_TOLERANCE_PCT = 2.0

DEFAULT_MAX_PRICE = 20.0
DEFAULT_MIN_DOLLAR_VOLUME = 300_000

PRICE_HISTORY_PERIOD = "1y"
RVOL_AVERAGE_WINDOW = 20


@dataclass(frozen=True)
class ScoreWeights:
    reverse_split: float = 20.0
    support_quality: float = 25.0
    touches: float = 20.0
    base_duration: float = 15.0
    volume_dryup: float = 10.0
    rvol_rise: float = 10.0

    def total(self) -> float:
        return (
            self.reverse_split
            + self.support_quality
            + self.touches
            + self.base_duration
            + self.volume_dryup
            + self.rvol_rise
        )


SCORE_WEIGHTS = ScoreWeights()
assert SCORE_WEIGHTS.total() == 100.0, "أوزان Phoenix Score يجب أن تجمع إلى 100"


IMPACTFUL_NEWS_KEYWORDS: List[str] = [
    "earnings", "eps", "quarterly results",
    "fda", "clinical trial", "approval",
    "merger", "acquisition", "acquire", "buyout",
    "contract", "partnership", "agreement",
    "offering", "dilution", "bankruptcy", "chapter 11",
]
NEWS_LOOKBACK_DAYS = 14

FINTEL_API_KEY = ""
IBORROWDESK_BASE_URL = "https://iborrowdesk.com/api/ticker"
