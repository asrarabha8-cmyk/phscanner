"""
config.py
---------
نقطة تجميع كل الإعدادات والقيم الافتراضية لمشروع Phoenix Scanner.
أي تعديل على الحدود أو الأوزان يجب أن يمر من هنا فقط، ولا يجب أن يتكرر
تعريف أي رقم "سحري" (magic number) داخل الطبقات الأخرى.
"""

from dataclasses import dataclass, field
from typing import List


# ---------------------------------------------------------------------------
# الأسواق المستهدفة
# ---------------------------------------------------------------------------
TARGET_EXCHANGES: List[str] = ["NYSE", "NASDAQ", "AMEX"]

# مصدر قوائم الرموز (NASDAQ Trader FTP - مجاني ورسمي)
NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"


# ---------------------------------------------------------------------------
# خيارات المستخدم في الواجهة (Reverse Split lookback)
# ---------------------------------------------------------------------------
REVERSE_SPLIT_LOOKBACK_OPTIONS = [30, 60, 90, 180]
DEFAULT_REVERSE_SPLIT_LOOKBACK = 90

SHORT_FLOAT_OPTIONS = [15, 20, 25]
DEFAULT_SHORT_FLOAT_MIN = 15

TOUCHES_OPTIONS = [3, 4, 5]
DEFAULT_MIN_TOUCHES = 3

# تم تخفيض الحد الأدنى بناءً على ملاحظة عملية: أغلب الأسهم تثبت 4-9
# جلسات قبل الارتداد الثاني، وهذا يطابق منهجية المعلم (7-10 أيام ثبات
# بدون كسر القاع). أُبقي 20/40/60 كخيارات لمن يريد قاعدة أطول وأكثر تحفظًا.
BASE_DAYS_OPTIONS = [7, 10, 20, 40, 60]
DEFAULT_MIN_BASE_DAYS = 7

DISTANCE_FROM_SUPPORT_OPTIONS = [2, 3, 5]
DEFAULT_MAX_DISTANCE_FROM_SUPPORT = 5.0

DEFAULT_SUPPORT_TOLERANCE_PCT = 2.0

# ---------------------------------------------------------------------------
# فلاتر مسبقة لتقليص الكون (Universe) قبل التحليل العميق (لأداء أفضل)
# هذه ليست من متطلبات المستخدم الأساسية، لكنها ضرورية عمليًا لأن تحليل
# آلاف الرموز واحدًا تلو الآخر عبر yfinance بطيء جدًا بدون تقليص أولي.
# ---------------------------------------------------------------------------
DEFAULT_MAX_PRICE = 20.0          # أسهم الـ Reverse Split غالبًا صغيرة القيمة
DEFAULT_MIN_DOLLAR_VOLUME = 300_000  # سيولة أدنى يوميًا لتجنب الأسهم الميتة

# ---------------------------------------------------------------------------
# نافذة البيانات التاريخية اللازمة لاكتشاف الدعم وجفاف الفوليوم
# ---------------------------------------------------------------------------
PRICE_HISTORY_PERIOD = "1y"       # مطلوب لتغطية أطول قاعدة (60 يوم) + سياق كافٍ
RVOL_AVERAGE_WINDOW = 20          # عدد الجلسات لحساب متوسط الفوليوم في RVOL

# ---------------------------------------------------------------------------
# أوزان Phoenix Score (المجموع = 100)
# القيم هنا تطابق المثال المذكور في متطلبات المشروع.
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# كلمات مفتاحية لاستبعاد الأخبار المؤثرة (المرحلة 1: فلترة بالكلمات المفتاحية)
# سيتم استبدال هذا في المرحلة 2 بمصدر أخبار حقيقي مهيكل (NLP / API متخصص).
# ---------------------------------------------------------------------------
IMPACTFUL_NEWS_KEYWORDS: List[str] = [
    "earnings", "eps", "quarterly results",
    "fda", "clinical trial", "approval",
    "merger", "acquisition", "acquire", "buyout",
    "contract", "partnership", "agreement",
    "offering", "dilution", "bankruptcy", "chapter 11",
]
NEWS_LOOKBACK_DAYS = 14

# ---------------------------------------------------------------------------
# مفاتيح API لمصادر بيانات المرحلة 2 (Short Float / Borrow Fee)
# تُترك فارغة الآن عمدًا؛ الأداة تعمل بدونها لكن بدون هذا الفلتر.
# ---------------------------------------------------------------------------
FINTEL_API_KEY = ""      # مثال لمزود Short Interest
IBORROWDESK_BASE_URL = "https://iborrowdesk.com/api/ticker"  # مجاني، بدون مفتاح
