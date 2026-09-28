"""
analysis/ema_calculator.py
----------------------------
يحسب المتوسطات المتحركة الأسية (EMA 20/50/200) ويحدد موضع السعر الحالي
بالنسبة لها -- مؤشر تأكيد إضافي حسب منهجية فيصل.
"""

from typing import Optional

_PERIODS = (20, 50, 200)


def calculate_ema_position(df) -> Optional[str]:
    """يرجع 'أسفل جميع EMA' / 'أعلى جميع EMA' / 'متداخل مع EMA' أو None."""
    if df is None or df.empty or len(df) < 20:
        return None

    close = df["Close"]
    last_price = float(close.iloc[-1])

    emas = {}
    for period in _PERIODS:
        if len(close) < period:
            continue
        emas[period] = float(close.ewm(span=period, adjust=False).mean().iloc[-1])

    if not emas:
        return None

    values = list(emas.values())
    if last_price < min(values):
        return "أسفل جميع EMA"
    if last_price > max(values):
        return "أعلى جميع EMA"
    return "متداخل مع EMA"
