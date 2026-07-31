"""
analysis/scorer.py
---------------------
يحوّل كل المكوّنات المكتشفة (دعم، فوليوم، Reverse Split، Short Interest)
إلى Phoenix Score من 100، باستخدام الأوزان المعرَّفة في config.SCORE_WEIGHTS.

كل دالة _score_* مستقلة ومُختبرة منطقيًا بمفردها، بحيث يسهل تعديل صيغة أي
مكوّن دون التأثير على الباقي.
"""

from config import (
    SCORE_WEIGHTS,
    TOUCHES_OPTIONS,
    BASE_DAYS_OPTIONS,
)
from core.models import (
    ReverseSplitInfo,
    ScoreBreakdown,
    SupportZone,
    VolumeProfile,
)


class PhoenixScorer:
    def __init__(self, tolerance_pct: float):
        self.tolerance_pct = tolerance_pct
        self.weights = SCORE_WEIGHTS

    def score(
        self,
        reverse_split: ReverseSplitInfo,
        support_zone: SupportZone,
        volume_profile: VolumeProfile,
    ) -> ScoreBreakdown:
        return ScoreBreakdown(
            reverse_split=self._score_reverse_split(reverse_split),
            support_quality=self._score_support_quality(support_zone),
            touches=self._score_touches(support_zone.touches),
            base_duration=self._score_base_duration(support_zone.base_days),
            volume_dryup=self._score_volume_dryup(volume_profile.dryup_ratio),
            rvol_rise=self._score_rvol(volume_profile.relative_volume),
        )

    # ------------------------------------------------------------------
    def _score_reverse_split(self, reverse_split: ReverseSplitInfo) -> float:
        # وجود Reverse Split هو شرط فلترة أساسي؛ إذا وصلنا لهذه المرحلة
        # فهو موجود دائمًا، لكن نُبقي المنطق هنا للوضوح والقابلية للتوسعة
        # (مثلاً: تفاوت النقاط حسب قوة نسبة الـ Reverse Split لاحقًا).
        return self.weights.reverse_split if reverse_split is not None else 0.0

    def _score_support_quality(self, zone: SupportZone) -> float:
        """
        جودة الدعم = مدى "ضيق" منطقة الارتدادات نسبةً للتسامح المسموح.
        كل الارتدادات قريبة جدًا من بعضها (عرض القاعدة << التسامح) تعني
        دعمًا أدق وأقوى.
        """
        if zone.zone_low <= 0:
            return 0.0

        actual_width_pct = (zone.zone_high - zone.zone_low) / zone.zone_low * 100
        if self.tolerance_pct <= 0:
            return 0.0

        tightness = 1.0 - min(actual_width_pct / self.tolerance_pct, 1.0)
        return round(self.weights.support_quality * tightness, 2)

    def _score_touches(self, touches: int) -> float:
        max_option = max(TOUCHES_OPTIONS)
        ratio = min(touches / max_option, 1.0)
        return round(self.weights.touches * ratio, 2)

    def _score_base_duration(self, base_days: int) -> float:
        max_option = max(BASE_DAYS_OPTIONS)
        ratio = min(base_days / max_option, 1.0)
        return round(self.weights.base_duration * ratio, 2)

    def _score_volume_dryup(self, dryup_ratio: float) -> float:
        """
        dryup_ratio = 0   -> جفاف كامل (النصف الثاني بدون فوليوم تقريبًا) = نقاط كاملة
        dryup_ratio >= 1  -> لا يوجد جفاف (الفوليوم ثابت أو يرتفع) = صفر
        """
        dryup_strength = max(0.0, 1.0 - dryup_ratio)
        return round(self.weights.volume_dryup * dryup_strength, 2)

    def _score_rvol(self, rvol: float) -> float:
        """
        نعطي نقاطًا كاملة عندما يبدأ RVOL بالارتفاع الواضح (>= 1.5),
        ونعطي صفرًا إن كان الفوليوم لا يزال هادئًا (<= 1.0).
        """
        if rvol <= 1.0:
            return 0.0
        ratio = min((rvol - 1.0) / 0.5, 1.0)
        return round(self.weights.rvol_rise * ratio, 2)
