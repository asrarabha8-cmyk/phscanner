"""
screener.py
-------------
Main orchestrator. This is the only layer that knows about both the
data_sources and analysis layers and wires them together; neither of
those layers knows about the other (Clean Architecture).

ترتيب المراحل (بعد الاشتراك بـ Polygon Stocks Starter -- طلبات غير محدودة):
1. الترشيح الأولي بالسعر/القيمة السوقية (NASDAQ Screener، مجاني وسريع)
   -- يقلل العدد من آلاف الأسهم لبضع مئات قبل أي طلب لـ Polygon
2. فحص Reverse Split (Polygon) على القائمة المصغّرة -- بالتوازي، بدون حدود
3. جلب السعر التاريخي (Polygon) فقط على الأسهم اللي عندها Reverse Split
4. باقي التحليل (Support, Volume, News, Short Interest، وفلتر الصعود
   بعد التقسيم)
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from typing import Callable, List, Optional

from config import PRICE_HISTORY_PERIOD, RVOL_AVERAGE_WINDOW, TARGET_EXCHANGES
from core.models import ScreenerParams, StockResult
from data_sources.base import (
    NewsSource,
    PriceDataSource,
    ReverseSplitSource,
    ShortInterestSource,
    UniverseSource,
)
from data_sources.news_source import YFinanceKeywordNewsSource
from data_sources.price_source import PolygonPriceSource
from data_sources.reverse_split_source import PolygonReverseSplitSource
from data_sources.short_interest_source import CompositeShortInterestSource
from data_sources.universe_source import NasdaqTraderUniverseSource
from data_sources.prefilter_source import get_prefiltered_tickers
from analysis.support_detector import SupportDetector
from analysis.volume_analyzer import VolumeAnalyzer
from analysis.scorer import PhoenixScorer

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, str], None]


class Screener:
    def __init__(
        self,
        price_source: Optional[PriceDataSource] = None,
        universe_source: Optional[UniverseSource] = None,
        reverse_split_source: Optional[ReverseSplitSource] = None,
        news_source: Optional[NewsSource] = None,
        short_interest_source: Optional[ShortInterestSource] = None,
        max_workers: int = 15,
    ):
        self.price_source = price_source or PolygonPriceSource()
        self.universe_source = universe_source or NasdaqTraderUniverseSource()
        self.reverse_split_source = reverse_split_source or PolygonReverseSplitSource()
        self.news_source = news_source or YFinanceKeywordNewsSource()
        self.short_interest_source = short_interest_source or CompositeShortInterestSource()
        self.max_workers = max_workers

    def run(
        self,
        params: ScreenerParams,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> List[StockResult]:
        # -------- المرحلة 1: الترشيح الأولي بالسعر/القيمة السوقية --------
        tickers = self.universe_source.get_tickers(TARGET_EXCHANGES)

        if progress_callback:
            progress_callback(0, len(tickers), "Pre-filtering by price/market cap...")

        tickers = get_prefiltered_tickers(
            tickers,
            max_price=params.max_price,
            min_dollar_volume=params.min_dollar_volume,
            min_price=params.min_price,
            max_market_cap=params.max_market_cap,
        )

        stage1_total = len(tickers)
        if progress_callback:
            progress_callback(0, stage1_total, f"{stage1_total} tickers passed pre-filter")

        # -------- المرحلة 2: فحص Reverse Split (Polygon) بالتوازي --------
        if progress_callback:
            progress_callback(0, stage1_total, "Checking Reverse Splits...")

        reverse_split_map = {}
        done_rs = 0
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_map = {
                executor.submit(
                    self.reverse_split_source.get_recent_reverse_splits,
                    ticker,
                    params.reverse_split_lookback_days,
                    date.today(),
                ): ticker
                for ticker in tickers
            }
            for future in as_completed(future_map):
                ticker = future_map[future]
                done_rs += 1
                try:
                    rs_info = future.result()
                    if rs_info is not None:
                        reverse_split_map[ticker] = rs_info
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Unexpected error checking reverse split for %s: %s", ticker, exc)

                if progress_callback and done_rs % 10 == 0:
                    progress_callback(done_rs, stage1_total, f"Reverse split check: {ticker}")

        surviving_tickers = list(reverse_split_map.keys())
        logger.warning(
            "المرحلة 2: %d من أصل %d سهم عندهم Reverse Split ضمن %d يوم",
            len(surviving_tickers),
            stage1_total,
            params.reverse_split_lookback_days,
        )

        total = len(surviving_tickers)
        if progress_callback:
            progress_callback(0, total, f"{total} tickers have a recent reverse split")

        if total == 0:
            return []

        # -------- المرحلة 3: جلب السعر التاريخي (Polygon) --------
        if progress_callback:
            progress_callback(0, total, "Fetching price data...")

        price_data = self.price_source.get_history_batch(
            surviving_tickers, period=PRICE_HISTORY_PERIOD
        )

        # -------- المرحلة 4: باقي التحليل --------
        results: List[StockResult] = []
        done_count = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_map = {
                executor.submit(
                    self._process_ticker,
                    ticker,
                    params,
                    price_data.get(ticker),
                    reverse_split_map[ticker],
                ): ticker
                for ticker in surviving_tickers
            }

            for future in as_completed(future_map):
                ticker = future_map[future]
                done_count += 1
                try:
                    result = future.result()
                    if result is not None:
                        results.append(result)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Unexpected error analyzing %s: %s", ticker, exc)

                if progress_callback and done_count % 10 == 0:
                    progress_callback(done_count, total, ticker)

        results.sort(key=lambda r: r.score.total, reverse=True)
        return results[: params.max_results]

    # ----------------------------------------------------------------
    def _check_post_split_rise(
        self, df, split_date: date, max_rise_pct: float
    ) -> bool:
        after_split = df[df.index.date >= split_date]
        if after_split.empty or len(after_split) < 2:
            return True

        first_close = float(after_split["Close"].iloc[0])
        if first_close <= 0:
            return True

        highest_after = float(after_split["High"].max())
        rise_pct = (highest_after - first_close) / first_close * 100

        return rise_pct <= max_rise_pct

    # ----------------------------------------------------------------
    def _process_ticker(
        self, ticker: str, params: ScreenerParams, df=None, reverse_split=None
    ) -> Optional[StockResult]:
        if df is None or df.empty or reverse_split is None:
            return None

        last_price = float(df["Close"].iloc[-1])
        if last_price > params.max_price or last_price < params.min_price:
            return None

        avg_dollar_volume = float((df["Close"] * df["Volume"]).tail(20).mean())
        if avg_dollar_volume < params.min_dollar_volume:
            return None

        if not self._check_post_split_rise(
            df, reverse_split.split_date, params.max_post_split_rise_pct
        ):
            return None

        detector = SupportDetector()
        support_zone = detector.detect(
            df,
            tolerance_pct=params.support_tolerance_pct,
            min_touches=params.min_touches,
            min_base_days=params.min_base_days,
        )
        if support_zone is None or support_zone.broken:
            return None

        zone_mid = (support_zone.zone_low + support_zone.zone_high) / 2
        distance_from_support_pct = (last_price - zone_mid) / zone_mid * 100
        if distance_from_support_pct > params.max_distance_from_support_pct:
            return None

        volume_analyzer = VolumeAnalyzer(rvol_window=RVOL_AVERAGE_WINDOW)
        volume_profile = volume_analyzer.analyze(df, support_zone.base_days)

        if params.exclude_impactful_news:
            news_check = self.news_source.check_impactful_news(ticker, lookback_days=14)
            if news_check.has_impactful_news:
                return None

        short_interest = self.short_interest_source.get_short_interest(ticker)
        if params.min_short_float_pct is not None and short_interest.short_float_pct is not None:
            if short_interest.short_float_pct < params.min_short_float_pct:
                return None

        scorer = PhoenixScorer(tolerance_pct=params.support_tolerance_pct)
        score = scorer.score(reverse_split, support_zone, volume_profile)

        return StockResult(
            ticker=ticker,
            price=last_price,
            support_zone=support_zone,
            distance_from_support_pct=distance_from_support_pct,
            reverse_split=reverse_split,
            volume_profile=volume_profile,
            short_interest=short_interest,
            score=score,
        )
