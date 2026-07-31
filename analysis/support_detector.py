"""
analysis/support_detector.py
-------------------------------
هذا هو قلب المشروع: اكتشاف "الدعم الحقيقي" — أي منطقة سعرية ارتد السهم منها
عدة مرات (وليس مجرد أدنى سعر تاريخي).

الخوارزمية بالخطوات:
  1. تحديد "القيعان المحلية" (Swing Lows): كل جلسة يكون سعرها الأدنى (Low)
     أقل من أو يساوي كل الجلسات المحيطة بها ضمن نافذة معينة.
  2. تجميع (Clustering) القيعان المحلية التي تقع ضمن نسبة تسامح (Tolerance)
     من بعضها في "مناطق دعم" مرشّحة.
  3. لكل منطقة مرشّحة: التحقق من عدم كسرها (لا إغلاق يومي تحتها) طوال
     الفترة من أول ارتداد فيها إلى اليوم.
  4. اختيار أفضل منطقة: الأقرب للسعر الحالي من بين المناطق التي حققت الحد
     الأدنى من الشروط (عدد ارتدادات + عدم كسر + مدة قاعدة).
"""

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

import numpy as np
import pandas as pd

from core.models import SupportZone


@dataclass
class _SwingLow:
    idx: int
    dt: date
    price: float


class SupportDetector:
    def __init__(self, swing_window: int = 3):
        """
        swing_window: عدد الجلسات على كل جانب لاعتبار نقطة "قاع محلي".
        قيمة 3 تعني: يجب أن يكون Low[i] أصغر أو يساوي كل من Low[i-3..i+3].
        """
        self.swing_window = swing_window

    # ------------------------------------------------------------------
    # الخطوة 1: القيعان المحلية
    # ------------------------------------------------------------------
    def _find_swing_lows(self, df: pd.DataFrame) -> List[_SwingLow]:
        lows = df["Low"].values
        n = len(lows)
        w = self.swing_window
        swings: List[_SwingLow] = []

        for i in range(w, n - w):
            window_slice = lows[i - w : i + w + 1]
            if lows[i] == window_slice.min():
                dt = df.index[i]
                swings.append(_SwingLow(idx=i, dt=dt.date(), price=float(lows[i])))
        return swings

    # ------------------------------------------------------------------
    # الخطوة 2: التجميع حسب التسامح السعري
    # ------------------------------------------------------------------
    def _cluster_swings(
        self, swings: List[_SwingLow], tolerance_pct: float
    ) -> List[List[_SwingLow]]:
        if not swings:
            return []

        sorted_swings = sorted(swings, key=lambda s: s.price)
        clusters: List[List[_SwingLow]] = []
        current_cluster: List[_SwingLow] = [sorted_swings[0]]

        for s in sorted_swings[1:]:
            cluster_min_price = min(c.price for c in current_cluster)
            relative_diff = (s.price - cluster_min_price) / cluster_min_price * 100
            if relative_diff <= tolerance_pct:
                current_cluster.append(s)
            else:
                clusters.append(current_cluster)
                current_cluster = [s]
        clusters.append(current_cluster)
        return clusters

    # ------------------------------------------------------------------
    # الخطوة 3: التحقق من عدم كسر منطقة معيّنة
    # ------------------------------------------------------------------
    def _is_zone_intact(
        self, df: pd.DataFrame, zone_low: float, first_touch_idx: int
    ) -> bool:
        """لا يوجد إغلاق يومي تحت zone_low من أول لمسة إلى آخر جلسة متاحة."""
        closes_after = df["Close"].iloc[first_touch_idx:]
        return bool((closes_after >= zone_low).all())

    # ------------------------------------------------------------------
    # الخطوة 4: الاختيار النهائي
    # ------------------------------------------------------------------
    def detect(
        self,
        df: pd.DataFrame,
        tolerance_pct: float,
        min_touches: int,
        min_base_days: int,
    ) -> Optional[SupportZone]:
        if df is None or df.empty or len(df) < (2 * self.swing_window + 1):
            return None

        swings = self._find_swing_lows(df)
        clusters = self._cluster_swings(swings, tolerance_pct)

        current_price = float(df["Close"].iloc[-1])
        last_idx = len(df) - 1

        candidates: List[SupportZone] = []

        for cluster in clusters:
            if len(cluster) < min_touches:
                continue

            zone_low = min(c.price for c in cluster)
            zone_high = max(c.price for c in cluster)
            first_touch = min(cluster, key=lambda c: c.idx)
            base_days = last_idx - first_touch.idx

            if base_days < min_base_days:
                continue

            intact = self._is_zone_intact(df, zone_low, first_touch.idx)

            # السعر الحالي يجب أن يكون فوق منطقة الدعم (وليس تحتها) لاعتبارها
            # ذات صلة حاليًا — دعم مكسور فعليًا لا قيمة له للمشروع.
            if current_price < zone_low:
                continue

            candidates.append(
                SupportZone(
                    zone_low=zone_low,
                    zone_high=zone_high,
                    touches=len(cluster),
                    touch_dates=[c.dt for c in cluster],
                    base_start_date=first_touch.dt,
                    base_days=base_days,
                    broken=not intact,
                )
            )

        # نستبعد كل المناطق المكسورة، ثم نختار الأقرب لسعر الإغلاق الحالي
        intact_candidates = [c for c in candidates if not c.broken]
        if not intact_candidates:
            return None

        best = min(
            intact_candidates,
            key=lambda z: abs(current_price - (z.zone_low + z.zone_high) / 2),
        )
        return best
