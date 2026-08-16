"""
analysis/rsi_calculator.py
------------------------------
يحسب مؤشر RSI (Relative Strength Index) القياسي على بيانات الإغلاق
اليومي. يُستخدم كإشارة تأكيد إضافية قبل الدخول (RSI < 30 يعني تشبّع
بيعي، مؤشر محتمل لارتداد قادم) -- زي ما وصف معلمك بمثال DRCT.

هذا مؤشر تأكيد يدوي المراجعة، مو فلتر استبعاد بالسكانر.
"""

import pandas as pd


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> float | None:
    """
    يرجع قيمة RSI الحالية (آخر يوم) بناءً على إغلاقات السعر.
    يرجع None لو البيانات غير كافية.
    """
    if df is None or len(df) < period + 1:
        return None

    closes = df["Close"]
    delta = closes.diff()

    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    last_avg_gain = avg_gain.iloc[-1]
    last_avg_loss = avg_loss.iloc[-1]

    if last_avg_loss == 0:
        return 100.0  # لا يوجد خسائر إطلاقًا خلال الفترة

    rs = last_avg_gain / last_avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi), 2)
