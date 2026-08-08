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
from datetime import date

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
    DEFAULT_SUPPORT_TOLERANCE_PCT,
    DISTANCE_FROM_SUPPORT_OPTIONS,
    REVERSE_SPLIT_LOOKBACK_OPTIONS,
    TOUCHES_OPTIONS,
)
from core.models import ScreenerParams
from data_sources.github_storage import read_tracked_stocks, write_tracked_stocks
from data_sources.price_source import PolygonPriceSource
from screener import Screener

logging.basicConfig(level=logging.WARNING)

st.set_page_config(page_title="Phoenix Scanner", layout="wide")

tab_scan, tab_tracked = st.tabs(["🔥 Scanner", "📊 Tracked Stocks"])

# ========================================================================
# التبويب الأول: السكانر
# ========================================================================
with tab_scan:
    st.title("🔥 Phoenix Scanner")
    st.caption(
        "Discover US accumulation stocks before the breakout -- based purely on "
        "price behavior, real support zones, and volume. No RSI / MACD / Stochastic."
    )

    with st.sidebar:
        st.header("⚙️ Screening Criteria")

        reverse_split_lookback = st.selectbox(
            "Reverse Split lookback (days)",
            REVERSE_SPLIT_LOOKBACK_OPTIONS,
            index=REVERSE_SPLIT_LOOKBACK_OPTIONS.index(DEFAULT_REVERSE_SPLIT_LOOKBACK),
        )

        max_post_split_rise = st.slider(
            "Max rise right after split (%)",
            min_value=10,
            max_value=200,
            value=50,
            step=10,
        )

        min_touches = st.selectbox(
            "Minimum touches on support",
            TOUCHES_OPTIONS,
            index=TOUCHES_OPTIONS.index(DEFAULT_MIN_TOUCHES),
        )

        tolerance_pct = st.slider(
            "Support zone tolerance (%)",
            min_value=0.5,
            max_value=10.0,
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

        enable_short_float = st.checkbox("Enable Short Float filter", value=True)
        max_short_float = None
        if enable_short_float:
            max_short_float = st.number_input(
                "Maximum Short Float (%)", min_value=0.0, max_value=100.0, value=20.0, step=1.0
            )
            st.caption(
                "Excludes stocks with short float above this threshold, "
                "per your mentor's rule (\"short less than 20%\")."
            )

        exclude_news = st.checkbox("Exclude stocks with impactful news", value=True)

        st.divider()
        st.subheader("Performance filters (to speed up scanning)")
        min_price = st.number_input(
            "Min stock price ($)", min_value=0.0, max_value=500.0, value=1.0
        )
        max_price = st.number_input(
            "Max stock price ($)", min_value=1.0, max_value=500.0, value=DEFAULT_MAX_PRICE
        )
        max_market_cap = st.number_input(
            "Max market cap ($)",
            min_value=1_000_000.0,
            value=300_000_000.0,
            step=50_000_000.0,
        )
        min_dollar_volume = st.number_input(
            "Min daily dollar volume ($)",
            min_value=0.0,
            value=float(DEFAULT_MIN_DOLLAR_VOLUME),
            step=50_000.0,
        )

        st.divider()
        st.subheader("Shares outstanding (float size)")
        min_shares_outstanding = st.number_input(
            "Min shares outstanding", min_value=0.0, value=500_000.0, step=100_000.0
        )
        max_shares_outstanding = st.number_input(
            "Max shares outstanding", min_value=0.0, value=3_000_000.0, step=100_000.0
        )

        max_results = st.slider("Max results shown", 10, 100, 50, step=10)

        run_button = st.button("🚀 Run Scan", type="primary", use_container_width=True)

    if run_button:
        params = ScreenerParams(
            reverse_split_lookback_days=reverse_split_lookback,
            max_post_split_rise_pct=max_post_split_rise,
            max_short_float_pct=max_short_float,
            min_touches=min_touches,
            min_base_days=min_base_days,
            support_tolerance_pct=tolerance_pct,
            max_distance_from_support_pct=max_distance,
            exclude_impactful_news=exclude_news,
            max_price=max_price,
            min_price=min_price,
            max_market_cap=max_market_cap,
            min_dollar_volume=min_dollar_volume,
            min_shares_outstanding=min_shares_outstanding,
            max_shares_outstanding=max_shares_outstanding,
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
            results, near_misses = screener.run(params, progress_callback=_on_progress)

        progress_bar.progress(1.0)
        status_text.empty()

        st.session_state["last_results"] = results
        st.session_state["last_near_misses"] = near_misses

    if "last_results" in st.session_state:
        results = st.session_state["last_results"]
        near_misses = st.session_state["last_near_misses"]

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

        if near_misses:
            st.divider()
            st.subheader("🔎 Near-miss stocks (worth a manual look)")
            st.caption(
                "These stocks failed one filter by a small margin -- review them "
                "yourself before deciding to skip."
            )
            near_rows = [n.to_row() for n in near_misses]
            df_near = pd.DataFrame(near_rows)
            st.dataframe(df_near, use_container_width=True, hide_index=True)

        st.caption("📌 All discovered tickers were saved to the Tracked Stocks tab.")
    else:
        st.info("Set your criteria in the sidebar, then click \"Run Scan\".")

# ========================================================================
# التبويب الثاني: سجل المتابعة
# ========================================================================
with tab_tracked:
    st.title("📊 Tracked Stocks")
    st.caption(
        "Every stock the scanner has ever found (results and near-misses), "
        "with its price at discovery and its most recent checked price."
    )

    tracked = read_tracked_stocks()

    if not tracked:
        st.info("No tracked stocks yet. Run a scan first.")
    else:
        col1, col2 = st.columns([1, 3])
        with col1:
            refresh_button = st.button(
                "🔄 Update current prices", use_container_width=True
            )

        if refresh_button:
            price_source = PolygonPriceSource()
            today = date.today()
            with st.spinner("Fetching current prices..."):
                tickers = list({s.ticker for s in tracked})
                price_data = price_source.get_history_batch(tickers)

                for s in tracked:
                    df = price_data.get(s.ticker)
                    if df is not None and not df.empty:
                        s.last_price = float(df["Close"].iloc[-1])
                        s.last_checked_date = today

            success = write_tracked_stocks(
                tracked, f"Update prices as of {today.isoformat()}"
            )
            if success:
                st.success("✅ Prices updated.")
            else:
                st.error("Failed to save updated prices. Check logs.")

        # -------- تصنيف كل سهم حسب "فئة" سبب الرفض (للتحليل الإحصائي) --------
        def _reason_category(reason: str) -> str:
            if reason == "passed":
                return "Passed all filters"
            if "صعد" in reason and "بعد التقسيم" in reason:
                return "Post-split rise too high"
            if "ارتدادات الدعم" in reason:
                return "Not enough support touches"
            if "الأسهم القائمة" in reason:
                return "Shares outstanding out of range"
            return "Other"

        # -------- ملخص متوسط الأداء لكل فئة (بس للأسهم اللي عندها سعر محدّث) --------
        checked = [s for s in tracked if s.change_pct is not None]
        if checked:
            st.subheader("📈 Average performance by rejection reason")
            summary_rows = {}
            for s in checked:
                cat = _reason_category(s.reason)
                summary_rows.setdefault(cat, []).append(s.change_pct)

            summary_data = [
                {
                    "Category": cat,
                    "Count": len(changes),
                    "Avg Change %": round(sum(changes) / len(changes), 2),
                    "Best %": round(max(changes), 2),
                    "Worst %": round(min(changes), 2),
                }
                for cat, changes in summary_rows.items()
            ]
            df_summary = pd.DataFrame(summary_data).sort_values(
                "Avg Change %", ascending=False
            )
            st.dataframe(df_summary, use_container_width=True, hide_index=True)
            st.divider()

        # -------- الجدول الكامل، مرتب تلقائيًا حسب الأداء (الأعلى ربحًا أولًا) --------
        rows = [s.to_row() for s in tracked]
        df_tracked = pd.DataFrame(rows)

        def _sort_key(val):
            return val if isinstance(val, (int, float)) else float("-inf")

        df_tracked["_sort"] = df_tracked["Change %"].apply(_sort_key)
        df_tracked = df_tracked.sort_values("_sort", ascending=False).drop(columns=["_sort"])
        st.dataframe(df_tracked, use_container_width=True, hide_index=True)
