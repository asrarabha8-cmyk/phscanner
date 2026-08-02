"""
core/models.py
--------------
كل نماذج البيانات (Data Models) المستخدمة عبر المشروع.
هذه الطبقة لا تحتوي على أي منطق تحليلي أو استدعاءات شبكة، فقط تعريف الهيكل.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional


@dataclass
class ScreenerParams:
    """كل المعايير القابلة للتحكم من واجهة المستخدم."""

    reverse_split_lookback_days: int = 90
    max_post_split_rise_pct: float = 20.0  # الحد الأقصى للصعود بعد التقسيم مباشرة
    min_price_drop_pct: float = 40.0
    decline_window_days: int = 30
    min_short_float_pct: Optional[float] = 15.0
    min_touches: int = 2
    min_base_days: int = 20
    support_tolerance_pct: float = 4.0
    max_distance_from_support_pct: float = 8.0
    exclude_impactful_news: bool = True

    # فلاتر أداء مسبقة (ليست من متطلبات المستخدم المباشرة لكنها ضرورية عمليًا)
    max_price: float = 10.00
    min_price: float = 1.0
    max_market_cap: float = 300_000_000  # 300 مليون دولار كبداية
    min_dollar_volume: float = 300_000
    max_results: int = 50


@dataclass
class ReverseSplitInfo:
    split_date: date
    ratio: float  # مثال: 1-for-10 تُخزَّن كـ 0.1


@dataclass
class SupportZone:
    """منطقة دعم مكتشفة: ليست سعرًا واحدًا بل نطاقًا ارتد السهم منه عدة مرات."""

    zone_low: float
    zone_high: float
    touches: int
    touch_dates: List[date]
    base_start_date: date
    base_days: int
    first_touch_low: float  # ذيل شمعة القاع الأول -- يُستخدم كوقف خسارة
    broken: bool  # True إذا كان هناك إغلاق يومي تحت الدعم خلال فترة القاعدة


@dataclass
class VolumeProfile:
    dryup_ratio: float          # < 1 يعني أن الفوليوم انخفض تدريجيًا (جيد)
    relative_volume: float      # RVOL الحالي


@dataclass
class NewsCheckResult:
    has_impactful_news: bool
    matched_headline: Optional[str] = None


@dataclass
class ShortInterestInfo:
    short_float_pct: Optional[float] = None
    borrow_fee_pct: Optional[float] = None
    available: bool = False


@dataclass
class ScoreBreakdown:
    reverse_split: float = 0.0
    support_quality: float = 0.0
    touches: float = 0.0
    base_duration: float = 0.0
    volume_dryup: float = 0.0
    rvol_rise: float = 0.0

    @property
    def total(self) -> float:
        return (
            self.reverse_split
            + self.support_quality
            + self.touches
            + self.base_duration
            + self.volume_dryup
            + self.rvol_rise
        )


@dataclass
class StockResult:
    """الصف النهائي الذي يُعرض في جدول الواجهة."""

    ticker: str
    price: float
    support_zone: SupportZone
    distance_from_support_pct: float
    reverse_split: ReverseSplitInfo
    volume_profile: VolumeProfile
    short_interest: ShortInterestInfo
    score: ScoreBreakdown

    def to_row(self) -> dict:
        return {
            "Ticker": self.ticker,
            "Price": round(self.price, 3),
            "Support Zone": f"{self.support_zone.zone_low:.2f} - {self.support_zone.zone_high:.2f}",
            "Stop Loss": round(self.support_zone.first_touch_low, 3),
            "Touches": self.support_zone.touches,
            "Base Days": self.support_zone.base_days,
            "Base Width %": round(
                (self.support_zone.zone_high - self.support_zone.zone_low)
                / self.support_zone.zone_low
                * 100,
                2,
            ),
            "Distance From Support %": round(self.distance_from_support_pct, 2),
            "Short Float %": (
                round(self.short_interest.short_float_pct, 2)
                if self.short_interest.short_float_pct is not None
                else "N/A"
            ),
            "Borrow Fee %": (
                round(self.short_interest.borrow_fee_pct, 2)
                if self.short_interest.borrow_fee_pct is not None
                else "N/A"
            ),
            "RVOL": round(self.volume_profile.relative_volume, 2),
            "Reverse Split Date": self.reverse_split.split_date.isoformat(),
            "Phoenix Score": round(self.score.total, 1),
        }


@dataclass
class NearMissResult:
    """سهم فشل بشرط واحد بفارق بسيط -- يُعرض بجدول منفصل للمراجعة اليدوية."""

    ticker: str
    price: float
    gap_description: str  # شرح مختصر لسبب القرب من التأهل

    def to_row(self) -> dict:
        return {
            "Ticker": self.ticker,
            "Price": round(self.price, 3),
            "Why it's close": self.gap_description,
        }
