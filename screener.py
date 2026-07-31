"""
screener.py
-------------
Main orchestrator. This is the only layer that knows about both the
data_sources and analysis layers and wires them together; neither of
those layers knows about the other (Clean Architecture).
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
from data_sources.price_source import YFinancePriceSource
from data_sources.reverse_split_source import YFinanceReverseSplitSource
from data_sources.short_interest_source import CompositeShortInterestSource
from data_sources.universe_source import NasdaqTraderUniverseSource
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
        max_workers: int = 8,
    ):
        self.price_source = price_source or YFinancePriceSource()
        self.universe_source = universe_source or NasdaqTraderUniverseSource()
        self.reverse_split_source = reverse_split_source or YFinanceReverseSplitSource()
        self.news_source = news_source or YFinanceKeywordNewsSource()
        self.short_interest_source = short_interest_source or CompositeShortInterestSource()
        self.max_workers = max_workers

    def run(
        self,
        params: ScreenerParams,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> List[StockResult]:
        tickers = self.universe_source.get_tickers(TARGET_EXCHANGES)
        total = len(tickers)
        if progress_callback:
            progress_callback(0, total, f"Loaded {total} tickers from target exchanges")

        # -------- المرحلة الجديدة: جلب كل بيانات الأسعار دفعة وحدة --------
        if progress_callback:
            progress_callback(0, total, "Fetching price data in batches...")

        price_data = self.price_source.get_history_batch(
            tickers, period=PRICE_HISTORY_PERIOD, batch_size=100
        )

        results: List[StockResult] = []
        done_count = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_map = {
                executor.submit(
                    self._process_ticker, ticker, params, price_data.get(ticker)
                ): ticker
                for ticker in tickers
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
    def _process_ticker(
        self, ticker: str, params: ScreenerParams, df=None
    ) -> Optional[StockResult]:
        # df يوصل جاهز من الـ batch fetch بدل ما يُطلب من الشبكة هنا
        if df is None or df.empty:
            return None

        last_price = float(df["Close"].iloc[-1])
        if last_price > params.max_price or last_price <= 0:
            return None

        avg_dollar_volume = float((df["Close"] * df["Volume"]).tail(20).mean())
        if avg_dollar_volume < params.min_dollar_volume:
            return None

        # -------- Condition 1: Reverse Split --------
        reverse_split = self.reverse_split_source.get_recent_reverse_splits(
            ticker, params.reverse_split_lookback_days, date.today()
        )
        if reverse_split is None:
            return None

        # -------- Conditions 5-8: real support --------
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

        # -------- Conditions 9-10: volume --------
        volume_analyzer = VolumeAnalyzer(rvol_window=RVOL_AVERAGE_WINDOW)
        volume_profile = volume_analyzer.analyze(df, support_zone.base_days)

        # -------- Condition 2: exclude impactful news --------
        if params.exclude_impactful_news:
            news_check = self.news_source.check_impactful_news(ticker, lookback_days=14)
            if news_check.has_impactful_news:
                return None

        # -------- Conditions 3-4: Short Float / Borrow Fee --------
        short_interest = self.short_interest_source.get_short_interest(ticker)
        if params.min_short_float_pct is not None and short_interest.short_float_pct is not None:
            if short_interest.short_float_pct < params.min_short_float_pct:
                return None

        # -------- Final scoring --------
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
