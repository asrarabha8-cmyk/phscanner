"""
app.py
--------
نقطة الدخول لواجهة Streamlit. هذا الملف مسؤول فقط عن العرض والتفاعل؛
كل المنطق الفعلي موجود في screener.py وطبقات analysis / data_sources.

تشغيل المشروع:
    pip install -r requirements.txt
    streamlit run app.py
"""

import logging

import pandas as pd
import streamlit as st

from config import (
    BASE_DAYS_OPTIONS,
    DEFAULT_MAX_DISTANCE_FROM_SUPPORT,
    DEFAULT_MAX_PRICE,
    DEFAULT_MIN_BASE_DAYS,
    DEFAULT_MIN_DOLLAR_VOLUME,
    DEFAULT_MIN_TOUCHES,
    DEFAULT_REVERSE_SPLIT_LOOKBACK,
    DEFAULT_SHORT_FLOAT_MIN,
    DEFAULT_SUPPORT_TOLERANCE_PCT,
    DISTANCE_FROM_SUPPORT_OPTIONS,
    REVERSE_SPLIT_LOOKBACK_OPTIONS,
    SHORT_FLOAT_OPTIONS,
    TOUCHES_OPTIONS,
)
from core.models import ScreenerParams
from screener import Screener

logging.basicConfig(level=logging.WARNING)

st.set_page_config(page_title="Phoenix Scanner", layout="wide")

st.title("🔥 Phoenix Scanner")
st.caption(
    "اكتشاف أسهم التجميع الأمريكية قبل الانفجار السعري — يعتمد على سلوك السعر "
    "ومناطق الدعم الحقيقية وحجم التداول فقط، بدون RSI / MACD / Stochastic."
)

# ----------------------------------------------------------------------
# الشريط الجانبي: كل المعايير القابلة للتحكم
# ----------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ معايير الفلترة")

    reverse_split_lookback = st.selectbox(
        "نطاق Reverse Split (يوم)",
        REVERSE_SPLIT_LOOKBACK_OPTIONS,
        index=REVERSE_SPLIT_LOOKBACK_OPTIONS.index(DEFAULT_REVERSE_SPLIT_LOOKBACK),
    )

    min_touches = st.selectbox(
        "عدد الارتدادات الأدنى من الدعم",
        TOUCHES_OPTIONS,
        index=TOUCHES_OPTIONS.index(DEFAULT_MIN_TOUCHES),
    )

    tolerance_pct = st.slider(
        "سماحية منطقة الدعم (Tolerance %)",
        min_value=0.5,
        max_value=5.0,
        value=DEFAULT_SUPPORT_TOLERANCE_PCT,
        step=0.5,
    )

    min_base_days = st.selectbox(
        "أقل مدة للقاعدة (جلسة)",
        BASE_DAYS_OPTIONS,
        index=BASE_DAYS_OPTIONS.index(DEFAULT_MIN_BASE_DAYS),
    )

    max_distance = st.selectbox(
        "أقصى مسافة من الدعم (%)",
        DISTANCE_FROM_SUPPORT_OPTIONS,
        index=DISTANCE_FROM_SUPPORT_OPTIONS.index(int(DEFAULT_MAX_DISTANCE_FROM_SUPPORT)),
    )

    st.divider()

    enable_short_float = st.checkbox("تفعيل فلتر Short Float", value=False)
    min_short_float = None
    if enable_short_float:
        min_short_float = st.selectbox(
            "أقل نسبة Short Float (%)",
            SHORT_FLOAT_OPTIONS,
            index=SHORT_FLOAT_OPTIONS.index(DEFAULT_SHORT_FLOAT_MIN),
        )
        st.caption(
            "⚠️ بيانات Short Float غير متوفرة مجانًا في هذه المرحلة لكل الأسهم. "
            "سيُطبَّق الفلتر فقط على الأسهم التي تتوفر لها بيانات."
        )

    exclude_news = st.checkbox("استبعاد الأسهم ذات الأخبار المؤثرة", value=True)

    st.divider()
    st.subheader("فلاتر أداء (لتسريع الفحص)")
    max_price = st.number_input(
        "أقصى سعر للسهم ($)", min_value=1.0, max_value=500.0, value=DEFAULT_MAX_PRICE
    )
    min_dollar_volume = st.number_input(
        "أقل سيولة يومية بالدولار ($)",
        min_value=0.0,
        value=float(DEFAULT_MIN_DOLLAR_VOLUME),
        step=50_000.0,
    )
    max_results = st.slider("أقصى عدد نتائج معروضة", 10, 100, 50, step=10)

    run_button = st.button("🚀 بدء الفحص", type="primary", use_container_width=True)

# ----------------------------------------------------------------------
# التنفيذ
# ----------------------------------------------------------------------
if run_button:
    params = ScreenerParams(
        reverse_split_lookback_days=reverse_split_lookback,
        min_short_float_pct=min_short_float,
        min_touches=min_touches,
        min_base_days=min_base_days,
        support_tolerance_pct=tolerance_pct,
        max_distance_from_support_pct=max_distance,
        exclude_impactful_news=exclude_news,
        max_price=max_price,
        min_dollar_volume=min_dollar_volume,
        max_results=max_results,
    )

    progress_bar = st.progress(0.0)
    status_text = st.empty()

    def _on_progress(done: int, total: int, current: str):
        ratio = 0.0 if total == 0 else min(done / total, 1.0)
        progress_bar.progress(ratio)
        status_text.text(f"تم فحص {done}/{total} — آخر رمز: {current}")

    with st.spinner("جاري الفحص... قد يستغرق هذا عدة دقائق حسب حجم السوق"):
        screener = Screener()
        results = screener.run(params, progress_callback=_on_progress)

    progress_bar.progress(1.0)
    status_text.empty()

    if not results:
        st.warning("لم يتم العثور على أسهم مطابقة للشروط الحالية. جرّب تخفيف الفلاتر.")
    else:
        st.success(f"✅ تم العثور على {len(results)} سهم مطابق")
        rows = [r.to_row() for r in results]
        df_results = pd.DataFrame(rows)
        st.dataframe(
            df_results.sort_values("Phoenix Score", ascending=False),
            use_container_width=True,
            hide_index=True,
        )
else:
    st.info("اضبط المعايير من الشريط الجانبي ثم اضغط «بدء الفحص».")