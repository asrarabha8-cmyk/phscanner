"""
app.py
--------
Entry point for the Streamlit UI. This file is responsible only for
display and interaction; all real logic lives in screener.py and the
analysis / data_sources layers.

To run:
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
    "Discover US accumulation stocks before the breakout -- based purely on "
    "price behavior, real support zones, and volume. No RSI / MACD / Stochastic."
)

# ----------------------------------------------------------------------
# Sidebar: every tunable filter
# ----------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Screening Criteria")

    reverse_split_lookback = st.selectbox(
        "Reverse Split lookback (days)",
        REVERSE_SPLIT_LOOKBACK_OPTIONS,
        index=REVERSE_SPLIT_LOOKBACK_OPTIONS.index(DEFAULT_REVERSE_SPLIT_LOOKBACK),
    )

    min_touches = st.selectbox(
        "Minimum touches on support",
        TOUCHES_OPTIONS,
        index=TOUCHES_OPTIONS.index(DEFAULT_MIN_TOUCHES),
    )

    tolerance_pct = st.slider(
        "Support zone tolerance (%)",
        min_value=0.5,
        max_value=5.0,
        value=DEFAULT_SUPPORT_TOLERANCE_PCT,
        step=0.5,
    )

    min_base_days = st.selectbox(
        "Minimum base duration (sessions)",
        BASE_DAYS_OPTIONS,
        index=BASE_DAYS_OPTIONS.index(DEFAULT_MIN_BASE_DAYS),
    )

    max_distance = st.selectbox(
        "Max distance from support (%)",
        DISTANCE_FROM_SUPPORT_OPTIONS,
        index=DISTANCE_FROM_SUPPORT_OPTIONS.index(int(DEFAULT_MAX_DISTANCE_FROM_SUPPORT)),
    )

    st.divider()

    enable_short_float = st.checkbox("Enable Short Float filter", value=False)
    min_short_float = None
    if enable_short_float:
        min_short_float = st.selectbox(
            "Minimum Short Float (%)",
            SHORT_FLOAT_OPTIONS,
            index=SHORT_FLOAT_OPTIONS.index(DEFAULT_SHORT_FLOAT_MIN),
        )
        st.caption(
            "Short Float data isn't freely available for every ticker in this "
            "phase. The filter only applies to tickers where data is available."
        )

    exclude_news = st.checkbox("Exclude stocks with impactful news", value=True)

    st.divider()
    st.subheader("Performance filters (to speed up scanning)")
    max_price = st.number_input(
        "Max stock price ($)", min_value=1.0, max_value=500.0, value=DEFAULT_MAX_PRICE
    )
    min_dollar_volume = st.number_input(
        "Min daily dollar volume ($)",
        min_value=0.0,
        value=float(DEFAULT_MIN_DOLLAR_VOLUME),
        step=50_000.0,
    )
    max_results = st.slider("Max results shown", 10, 100, 50, step=10)

    run_button = st.button("🚀 Run Scan", type="primary", use_container_width=True)

# ----------------------------------------------------------------------
# Execution
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
        status_text.text(f"Scanned {done}/{total} -- last ticker: {current}")

    with st.spinner("Scanning... this can take several minutes depending on market size"):
        screener = Screener()
        results = screener.run(params, progress_callback=_on_progress)

    progress_bar.progress(1.0)
    status_text.empty()

    if not results:
        st.warning("No matching stocks found. Try loosening the filters.")
    else:
        st.success(f"✅ Found {len(results)} matching stocks")
        rows = [r.to_row() for r in results]
        df_results = pd.DataFrame(rows)
        st.dataframe(
            df_results.sort_values("Phoenix Score", ascending=False),
            use_container_width=True,
            hide_index=True,
        )
else:
    st.info("Set your criteria in the sidebar, then click \"Run Scan\".")
