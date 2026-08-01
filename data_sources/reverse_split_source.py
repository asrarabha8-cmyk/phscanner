"""
analysis/reverse_split_detector.py
-------------------------------------
يكتشف Reverse Split محليًا من بيانات السعر والفوليوم نفسها (اللي أصلاً
عندنا من Twelve Data)، بدون أي طلب لمصدر بيانات خارجي منفصل.

الفكرة: عند حدوث Reverse Split بنسبة N-for-1 (مثال: 1-for-10)، يصير:
  - قفزة مفاجئة في السعر بين إغلاق يوم وافتتاح اليوم التالي بمعامل قريب من N
  - انخفاض متزامن في الفوليوم بنفس المعامل تقريبًا (لأن عدد الأسهم
    المتداولة يتقلّص بنفس النسبة)
هذا النمط المزدوج (سعر × فوليوم معًا) يميّز Reverse Split عن أي قفزة
سعرية عادية ناتجة عن خبر أو تقلب سوق طبيعي.
"""

from datetime import date
from typing import Optional

import pandas as pd

from core.models import ReverseSplitInfo

# النسب الشائعة لل Reverse Split (N-for-1)
_COMMON_RATIOS = [2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50]
_PRICE_TOLERANCE = 0.12          # هامش تسامح 12% حول النسبة المتوقعة
_MAX_VOLUME_RATIO_MARGIN = 0.4   # هامش سماح فوق الانخفاض المتوقع بالفوليوم


def detect_reverse_split(
    df: pd.DataFrame, lookback_days: int, as_of: date
) -> Optional[ReverseSplitInfo]:
    if df is None or len(df) < 2:
        return None

    cutoff = pd.Timestamp(as_of) - pd.Timedelta(days=lookback_days)
    closes = df["Close"].values
    opens = df["Open"].values
    volumes = df["Volume"].values
    dates = df.index

    best_match: Optional[ReverseSplitInfo] = None

    for i in range(1, len(df)):
        dt = dates[i]
        if dt < cutoff:
            continue

        prev_close = closes[i - 1]
        today_open = opens[i]
        if prev_close <= 0 or today_open <= 0:
            continue

        price_ratio = today_open / prev_close
        if price_ratio <= 1.3:
            continue  # مو قفزة كبيرة كفاية لتكون Reverse Split

        prev_volume = volumes[i - 1]
        today_volume = volumes[i]

        for n in _COMMON_RATIOS:
            expected = float(n)
            if abs(price_ratio - expected) / expected <= _PRICE_TOLERANCE:
                if prev_volume > 0:
                    volume_ratio = today_volume / prev_volume
                    if volume_ratio <= (1 / expected) * (1 + _MAX_VOLUME_RATIO_MARGIN):
                        best_match = ReverseSplitInfo(
                            split_date=dt.date(), ratio=1.0 / expected
                        )
                break

    return best_match
