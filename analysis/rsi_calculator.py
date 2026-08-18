"""
analysis/rsi_calculator.py
------------------------------
يحسب مؤشر RSI باستخدام طريقة Wilder الأصلية (المعيار القياسي المستخدم
بمعظم منصات التداول مثل TradingView). يُستخدم كإشارة تأكيد إضافية قبل
الدخول (RSI < 30 يعني تشبّع بيعي، مؤشر محتمل لارتداد قادم) -- زي ما
وصف معلمك بمثال DRCT.

هذا مؤشر تأكيد يدوي المراجعة، مو فلتر استبعاد بالسكانر.
"""

from typing import Optional

import pandas as pd


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> Optional[float]:
    """
    يرجع قيمة RSI الحالية (آخر يوم) باستخدام تنعيم Wilder:
    1. أول متوسط ربح/خسارة = متوسط بسيط لأول `period` فترة.
    2. كل فترة بعدها: المتوسط الجديد = ((المتوسط السابق × (period-1)) + القيمة الحالية) / period
    يرجع None لو البيانات غير كافية.
    """
    if df is None or len(df) < period + 1:
        return None

    closes = df["Close"]
    delta = closes.diff().dropna()

    gains = delta.where(delta > 0, 0.0)
    losses = -delta.where(delta < 0, 0.0)

    if len(gains) < period:
        return None

    # الخطوة 1: أول متوسط = متوسط بسيط لأول `period` قيمة
    avg_gain = gains.iloc[:period].mean()
    avg_loss = losses.iloc[:period].mean()

    # الخطوة 2: تنعيم Wilder لبقية الفترات (EMA بمعامل 1/period)
    for i in range(period, len(gains)):
        avg_gain = ((avg_gain * (period - 1)) + gains.iloc[i]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses.iloc[i]) / period

    if avg_loss == 0:
        return 100.0  # لا يوجد خسائر إطلاقًا خلال كل الفترة

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi), 2)
