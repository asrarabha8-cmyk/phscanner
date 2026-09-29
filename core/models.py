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
    max_post_split_rise_pct: float = 1000.0  # سقف أمان فقط، مو فلتر حقيقي
    min_price_drop_pct: float = 40.0
    decline_window_days: int = 30
    max_short_float_pct: Optional[float] = 20.0
    min_touches: int = 2
    min_base_days: int = 7
    support_tolerance_pct: float = 4.0
    max_distance_from_support_pct: float = 8.0
    exclude_impactful_news: bool = True

    max_price: float = 10.00
    min_price: float = 1.0
    max_market_cap: float = 300_000_000
    min_shares_outstanding: float = 200_000
    max_shares_outstanding: float = 8_000_000
    min_dollar_volume: float = 300_000
    max_results: int = 50


@dataclass
class ReverseSplitInfo:
    split_date: date
    ratio: float


@dataclass
class SupportZone:
    zone_low: float
    zone_high: float
    touches: int
    touch_dates: List[date]
    base_start_date: date
    base_days: int
    first_touch_low: float
    broken: bool


@dataclass
class VolumeProfile:
    dryup_ratio: float
    relative_volume: float


@dataclass
class NewsCheckResult:
    has_impactful_news: bool
    matched_headline: Optional[str] = None


@dataclass
class ShortInterestInfo:
    short_float_pct: Optional[float] = None
    short_interest_shares: Optional[float] = None
    borrow_fee_pct: Optional[float] = None
    available: bool = False


def _short_interest_label(shares: Optional[float], pct: Optional[float] = None) -> str:
    """يصنف مستوى الشورت.

    نحسب تصنيفًا من العدد المطلق للأسهم، وتصنيفًا آخر من النسبة المئوية،
    ثم نأخذ الأفضل (الأقل خطورة) بين الاثنين دائمًا -- لأن سهمًا بعدد أسهم
    قائمة كبير قد يكون له عدد شورت مرتفع ظاهريًا لكنه ضئيل نسبيًا، والعكس صحيح.
    """

    def _level_from_shares(s: Optional[float]) -> Optional[int]:
        if s is None:
            return None
        if s < 20_000:
            return 1
        if s >= 50_000:
            return 3
        return 2

    def _level_from_pct(p: Optional[float]) -> Optional[int]:
        if p is None:
            return None
        if p < 20.0:
            return 1
        if p >= 50.0:
            return 3
        return 2

    levels = [lvl for lvl in (_level_from_shares(shares), _level_from_pct(pct)) if lvl is not None]
    if not levels:
        return "N/A"

    best = min(levels)
    if best == 1:
        return "🟢 قليل"
    if best == 3:
        return "🔴 عالٍ"
    return "🟡 متوسط"


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
    ticker: str
    price: float
    support_zone: SupportZone
    distance_from_support_pct: float
    reverse_split: ReverseSplitInfo
    volume_profile: VolumeProfile
    short_interest: ShortInterestInfo
    score: ScoreBreakdown
    rsi: Optional[float] = None
    post_split_rise_pct: float = 0.0
    ema_position: Optional[str] = None
    low_liquidity: bool = False
    avg_dollar_volume: Optional[float] = None

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
            "Post-Split Rise %": round(self.post_split_rise_pct, 1),
            "Short Float %": (
                round(self.short_interest.short_float_pct, 2)
                if self.short_interest.short_float_pct is not None
                else "N/A"
            ),
            "Short Interest (shares)": (
                f"{self.short_interest.short_interest_shares:,.0f}"
                if self.short_interest.short_interest_shares is not None
                else "N/A"
            ),
            "Short Level": _short_interest_label(
                self.short_interest.short_interest_shares,
                self.short_interest.short_float_pct,
            ),
            "Borrow Fee %": (
                round(self.short_interest.borrow_fee_pct, 2)
                if self.short_interest.borrow_fee_pct is not None
                else "N/A"
            ),
            "RSI": round(self.rsi, 1) if self.rsi is not None else "N/A",
            "RVOL": round(self.volume_profile.relative_volume, 2),
            "EMA": self.ema_position if self.ema_position is not None else "N/A",
            "Low Liquidity": "⚠️ نعم" if self.low_liquidity else "لا",
            "Avg $ Volume": (
                f"{self.avg_dollar_volume:,.0f}$" if self.avg_dollar_volume is not None else "N/A"
            ),
            "Reverse Split Date": self.reverse_split.split_date.isoformat(),
            "Phoenix Score": round(self.score.total, 1),
        }


@dataclass
class NearMissResult:
    ticker: str
    price: float
    gap_description: str
    short_float_pct: Optional[float] = None
    short_interest_shares: Optional[float] = None
    borrow_fee_pct: Optional[float] = None
    rsi: Optional[float] = None
    # الحقول التالية متاحة فقط لما يكون سبب الاستبعاد "عدد ارتدادات الدعم"
    touches: Optional[int] = None
    base_days: Optional[int] = None
    post_split_rise_pct: Optional[float] = None
    stop_loss: Optional[float] = None
    ema_position: Optional[str] = None

    def to_row(self) -> dict:
        return {
            "Ticker": self.ticker,
            "Price": round(self.price, 3),
            "Why it's close": self.gap_description,
            "Short Float %": (
                round(self.short_float_pct, 2) if self.short_float_pct is not None else "N/A"
            ),
            "Short Interest (shares)": (
                f"{self.short_interest_shares:,.0f}"
                if self.short_interest_shares is not None
                else "N/A"
            ),
            "Short Level": _short_interest_label(self.short_interest_shares, self.short_float_pct),
            "Borrow Fee %": (
                round(self.borrow_fee_pct, 2) if self.borrow_fee_pct is not None else "N/A"
            ),
            "RSI": round(self.rsi, 1) if self.rsi is not None else "N/A",
            "EMA": self.ema_position if self.ema_position is not None else "N/A",
        }


@dataclass
class TrackedStock:
    """سجل دائم لسهم اكتُشف بالسكانر -- يُستخدم لمتابعة أدائه بمرور الوقت."""

    ticker: str
    discovery_date: date
    discovery_price: float
    kind: str
    reason: str
    last_checked_date: Optional[date] = None
    last_price: Optional[float] = None
    touches: Optional[int] = None
    base_days: Optional[int] = None
    rsi: Optional[float] = None
    short_interest_shares: Optional[float] = None
    post_split_rise_pct: Optional[float] = None
    stop_loss: Optional[float] = None
    phoenix_score: Optional[float] = None
    ema_position: Optional[str] = None
    cycle_stage: Optional[int] = None
    cycle_stage_label: Optional[str] = None

    @property
    def change_pct(self) -> Optional[float]:
        if self.last_price is None or self.discovery_price <= 0:
            return None
        return round((self.last_price - self.discovery_price) / self.discovery_price * 100, 2)

    def to_row(self) -> dict:
        return {
            "Ticker": self.ticker,
            "Type": "Result" if self.kind == "result" else "Near-miss",
            "Discovery Date": self.discovery_date.isoformat(),
            "Discovery Price": round(self.discovery_price, 3),
            "Last Checked": self.last_checked_date.isoformat() if self.last_checked_date else "N/A",
            "Last Price": round(self.last_price, 3) if self.last_price is not None else "N/A",
            "Change %": self.change_pct if self.change_pct is not None else "N/A",
            "Reason": self.reason,
            "Touches": self.touches if self.touches is not None else "N/A",
            "Base Days": self.base_days if self.base_days is not None else "N/A",
            "RSI": round(self.rsi, 1) if self.rsi is not None else "N/A",
            "Short Interest (shares)": (
                f"{self.short_interest_shares:,.0f}"
                if self.short_interest_shares is not None
                else "N/A"
            ),
            "Post-Split Rise %": (
                round(self.post_split_rise_pct, 1)
                if self.post_split_rise_pct is not None
                else "N/A"
            ),
            "Stop Loss": round(self.stop_loss, 3) if self.stop_loss is not None else "N/A",
            "Phoenix Score": (
                round(self.phoenix_score, 1) if self.phoenix_score is not None else "N/A"
            ),
            "EMA": self.ema_position if self.ema_position is not None else "N/A",
            "Cycle Stage": self.cycle_stage if self.cycle_stage is not None else "N/A",
            "Cycle Stage Label": self.cycle_stage_label if self.cycle_stage_label is not None else "N/A",
        }
