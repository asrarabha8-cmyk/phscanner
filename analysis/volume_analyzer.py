"""
analysis/volume_analyzer.py
------------------------------
1. جفاف الفوليوم (Volume Dry-up): نقسّم فترة القاعدة إلى نصفين ونقارن
   متوسط الفوليوم بينهما. dryup_ratio < 1 يعني أن الفوليوم في النصف
   الثاني (الأحدث) أقل من النصف الأول — علامة على انتهاء البيع.

2. Relative Volume (RVOL): فوليوم آخر جلسة مقسومًا على متوسط فوليوم
   نافذة سابقة (بدون تضمين آخر جلسة في المتوسط نفسه لتجنب التحيّز).
"""

import pandas as pd

from core.models import VolumeProfile


class VolumeAnalyzer:
    def __init__(self, rvol_window: int = 20):
        self.rvol_window = rvol_window

    def analyze(self, df: pd.DataFrame, base_days: int) -> VolumeProfile:
        volumes = df["Volume"]

        base_slice = volumes.iloc[-base_days:] if base_days > 0 else volumes
        dryup_ratio = self._compute_dryup_ratio(base_slice)
        rvol = self._compute_rvol(volumes)

        return VolumeProfile(dryup_ratio=dryup_ratio, relative_volume=rvol)

    def _compute_dryup_ratio(self, base_volumes: pd.Series) -> float:
        if len(base_volumes) < 4:
            return 1.0  # بيانات غير كافية للمقارنة -> نعتبرها محايدة

        mid = len(base_volumes) // 2
        first_half_avg = base_volumes.iloc[:mid].mean()
        second_half_avg = base_volumes.iloc[mid:].mean()

        if first_half_avg == 0:
            return 1.0
        return float(second_half_avg / first_half_avg)

    def _compute_rvol(self, volumes: pd.Series) -> float:
        if len(volumes) < self.rvol_window + 1:
            return 1.0

        last_volume = volumes.iloc[-1]
        avg_volume = volumes.iloc[-(self.rvol_window + 1) : -1].mean()

        if avg_volume == 0:
            return 1.0
        return float(last_volume / avg_volume)
