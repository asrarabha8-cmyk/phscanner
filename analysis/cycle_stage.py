"""
analysis/cycle_stage.py
------------------------
يحدد "مرحلة دورة الدعم" لسهم معين (قاع -> ثبات -> ارتداد -> اختبار -> تأكيد)
بناءً على بيانات محسوبة مسبقًا عندنا (نسبة الارتداد، عدد ملامسات الدعم).

تفسير تقريبي لمنهجية فيصل مبني على البيانات المتوفرة فعليًا بالسكانر --
قابل للتعديل حسب الملاحظة الفعلية.
"""

from typing import Optional, Tuple

STAGE_LABELS = {
    1: "قاع",
    2: "ثبات",
    3: "ارتداد",
    4: "اختبار",
    5: "تأكيد",
}


def determine_cycle_stage(
    passed: bool,
    touches: Optional[int],
    rise_pct: Optional[float],
) -> Tuple[Optional[int], Optional[str]]:
    if passed:
        return 5, STAGE_LABELS[5]

    if touches is not None and touches >= 1:
        return 4, STAGE_LABELS[4]

    if rise_pct is not None:
        if rise_pct >= 10:
            return 3, STAGE_LABELS[3]
        if rise_pct > 0:
            return 2, STAGE_LABELS[2]
        return 1, STAGE_LABELS[1]

    return None, None
