"""
screener.py
-------------
Main orchestrator. This is the only layer that knows about both the
data_sources and analysis layers and wires them together; neither of
those layers knows about the other (Clean Architecture).

تحديث مهم: بناءً على تحليل بيانات فعلية على 3+ أسابيع، الصعود القوي بعد
التقسيم لم يعد سبب استبعاد -- أصبح عامل تعزيز إيجابي بالـScore. يبقى فقط
سقف أمان (sanity ceiling) لاستبعاد الحالات الشاذة جدًا (احتيال محتمل أو
خطأ بيانات)، لا فلترة حقيقية.

تحديث: الأسهم اللي تفشل بس بسبب سيولة يومية ضعيفة (dollar volume) ما تُرفض
نهائيًا -- تُسجَّل كـ"قريبة من التأهل" (near-miss) لأن هذا بالضبط نمط
الأسهم صغيرة الـ float اللي ممكن تنفجر فجأة (مثال حقيقي: MSGY).

تحديث آخر: أضفنا حساب EMA (موضع السعر من المتوسطات) و"مرحلة دورة الدعم"
(قاع/ثبات/ارتداد/اختبار/تأكيد) -- مقتبسة من منهجية فيصل، تُحسب لكل الأسهم
اللي عندها Reverse Split بغض النظر عن نجاحها، وتُنشر لصفحة المراقبة
الثابتة (monitor.html) عبر نفس ملف tracked_stocks.csv.

ترتيب المراحل:
1. الترشيح الأولي بالسعر/القيمة السوقية (NASDAQ Screener، مجاني وسريع)
2. فحص Reverse Split (Polygon) على القائمة المصغّرة
3. جلب السعر التاريخي (Polygon، وقت السوق الرسمي فقط) فقط على الأسهم
   اللي عندها Reverse Split
4. باقي التحليل (شامل فلتر عدد الأسهم القائمة، RSI والشورت الخام
   كمؤشرات تأكيد إضافية)، مع تصنيف الأسهم "القريبة من التأهل" في
   قائمة منفصلة
5. حفظ كل النتائج (رئيسية + قريبة) بسجل المتابعة الدائم على GitHub،
   مع خصائصها وقت الاكتشاف (RSI/ملامسات/شورت/سكور/وقف خسارة/EMA/مرحلة
   الدورة) عشان نقدر لاحقًا نقارن خصائص الفائزين بالخاسرين إحصائيًا.
"""

import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from typing import Callable, List, Optional, Tuple

from config import PRICE_HISTORY_PERIOD, RVOL_AVERAGE_WINDOW, TARGET_EXCHANGES
from core.models import NearMissResult, ScreenerParams, StockResult, TrackedStock
from data_sources.base import (
    NewsSource,
    PriceDataSource,
    ReverseSplitSource,
    ShortInterestSource,
    UniverseSource,
)
from data_sources.github_storage import add_new_tracked_stocks
from data_sources.news_source import YFinanceKeywordNewsSource
from data_sources.price_source import PolygonPriceSource
from data_sources.reverse_split_source import PolygonReverseSplitSource
from data_sources.shares_outstanding_source import get_shares_outstanding
from data_sources.short_interest_source import CompositeShortInterestSource
from data_sources.universe_source import NasdaqTraderUniverseSource
from data_sources.prefilter_source import get_prefiltered_tickers
from analysis.support_detector import SupportDetector
from analysis.volume_analyzer import VolumeAnalyzer
from analysis.rsi_calculator import calculate_rsi
from analysis.ema_calculator import calculate_ema_position
from analysis.cycle_stage import determine_cycle_stage
from analysis.scorer import PhoenixScorer

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, str], None]

_NEAR_MISS_SHARES_MARGIN_RATIO = 0.25
# سقف أمان فقط (مو فلتر حقيقي) -- يستبعد فقط الحالات الشاذة جدًا
_SANITY_CEILING_RISE_PCT = 1000.0


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
    ) -> Tuple[List[StockResult], List[NearMissResult]]:
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
            return [], []

        if progress_callback:
            progress_callback(0, total, "Fetching price data...")

        price_data = self.price_source.get_history_batch(
            surviving_tickers, period=PRICE_HISTORY_PERIOD
        )

        results: List[StockResult] = []
        near_misses: List[NearMissResult] = []
        rejection_reasons: Counter = Counter()
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
                    result, reason, near_miss = future.result()
                    if result is not None:
                        results.append(result)
                    else:
                        rejection_reasons[reason] += 1
                        if near_miss is not None:
                            near_misses.append(near_miss)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Unexpected error analyzing %s: %s", ticker, exc)
                    rejection_reasons["exception"] += 1

                if progress_callback and done_count % 10 == 0:
                    progress_callback(done_count, total, ticker)

        logger.warning(
            "المرحلة 4: ملخص الاستبعاد من أصل %d سهم -- %s -- %d سهم قريب من التأهل",
            total,
            dict(rejection_reasons.most_common()),
            len(near_misses),
        )

        results.sort(key=lambda r: r.score.total, reverse=True)
        near_misses.sort(key=lambda n: n.gap_description)

        today = date.today()
        tracked_new = []
        for r in results:
            stage_num, stage_label = determine_cycle_stage(
                passed=True, touches=r.support_zone.touches, rise_pct=r.post_split_rise_pct
            )
            tracked_new.append(
                TrackedStock(
                    ticker=r.ticker,
                    discovery_date=today,
                    discovery_price=r.price,
                    kind="result",
                    reason="passed",
                    touches=r.support_zone.touches,
                    base_days=r.support_zone.base_days,
                    rsi=r.rsi,
                    short_interest_shares=r.short_interest.short_interest_shares,
                    post_split_rise_pct=r.post_split_rise_pct,
                    stop_loss=r.support_zone.first_touch_low,
                    phoenix_score=r.score.total,
                    ema_position=r.ema_position,
                    cycle_stage=stage_num,
                    cycle_stage_label=stage_label,
                )
            )
        for n in near_misses:
            stage_num, stage_label = determine_cycle_stage(
                passed=False, touches=n.touches, rise_pct=n.post_split_rise_pct
            )
            tracked_new.append(
                TrackedStock(
                    ticker=n.ticker,
                    discovery_date=today,
                    discovery_price=n.price,
                    kind="near_miss",
                    reason=n.gap_description,
                    touches=n.touches,
                    base_days=n.base_days,
                    rsi=n.rsi,
                    short_interest_shares=n.short_interest_shares,
                    post_split_rise_pct=n.post_split_rise_pct,
                    stop_loss=n.stop_loss,
                    phoenix_score=None,
                    ema_position=n.ema_position,
                    cycle_stage=stage_num,
                    cycle_stage_label=stage_label,
                )
            )

        if tracked_new:
            try:
                add_new_tracked_stocks(tracked_new)
            except Exception as exc:  # noqa: BLE001
                logger.warning("فشل حفظ سجل المتابعة: %s", exc)

        return results[: params.max_results], near_misses

    # ----------------------------------------------------------------
    def _calc_post_split_rise(self, df, split_date: date) -> float:
        """يرجع نسبة الصعود فقط، بدون أي حكم قبول/رفض."""
        after_split = df[df.index.date >= split_date]
        if after_split.empty or len(after_split) < 2:
            return 0.0

        first_close = float(after_split["Close"].iloc[0])
        if first_close <= 0:
            return 0.0

        highest_after = float(after_split["High"].max())
        return (highest_after - first_close) / first_close * 100

    # ----------------------------------------------------------------
    def _process_ticker(
        self, ticker: str, params: ScreenerParams, df=None, reverse_split=None
    ) -> Tuple[Optional[StockResult], str, Optional[NearMissResult]]:
        if df is None or df.empty:
            return None, "no_price_data", None
        if reverse_split is None:
            return None, "no_reverse_split", None

        last_price = float(df["Close"].iloc[-1])
        if last_price > params.max_price or last_price < params.min_price:
            return None, "price_out_of_range", None

        rsi = calculate_rsi(df)
        ema_position = calculate_ema_position(df)
        # يُحسب مبكرًا (بدل بعد فلتر السيولة) عشان يتوفر لكل حالات near-miss
        rise_pct = self._calc_post_split_rise(df, reverse_split.split_date)

        shares_outstanding = get_shares_outstanding(ticker)
        if shares_outstanding is None:
            return None, "no_shares_outstanding_data", None
        if not (
            params.min_shares_outstanding
            <= shares_outstanding
            <= params.max_shares_outstanding
        ):
            margin_low = params.min_shares_outstanding * (1 - _NEAR_MISS_SHARES_MARGIN_RATIO)
            margin_high = params.max_shares_outstanding * (1 + _NEAR_MISS_SHARES_MARGIN_RATIO)
            if margin_low <= shares_outstanding <= margin_high:
                short_interest = self.short_interest_source.get_short_interest(ticker)
                near_miss = NearMissResult(
                    ticker=ticker,
                    price=last_price,
                    gap_description=(
                        f"عدد الأسهم القائمة {shares_outstanding:,.0f} خارج النطاق "
                        f"({params.min_shares_outstanding:,.0f} - {params.max_shares_outstanding:,.0f})"
                    ),
                    short_float_pct=short_interest.short_float_pct,
                    short_interest_shares=short_interest.short_interest_shares,
                    borrow_fee_pct=short_interest.borrow_fee_pct,
                    rsi=rsi,
                    ema_position=ema_position,
                )
                return None, "shares_outstanding_out_of_range", near_miss
            return None, "shares_outstanding_out_of_range", None

        # -------- سيولة يومية ضعيفة: مو رفض نهائي، تسجَّل كـ"مراقبة" --------
        # أسهم float صغير جدًا (نجتاز فحص عدد الأسهم القائمة فوق) ممكن
        # تكون خاملة السيولة لفترة ثم تنفجر فجأة بيوم واحد (مثال: MSGY).
        avg_dollar_volume = float((df["Close"] * df["Volume"]).tail(20).mean())
        if avg_dollar_volume < params.min_dollar_volume:
            short_interest = self.short_interest_source.get_short_interest(ticker)
            near_miss = NearMissResult(
                ticker=ticker,
                price=last_price,
                gap_description=(
                    f"سيولة يومية ضعيفة {avg_dollar_volume:,.0f}$ "
                    f"(المطلوب {params.min_dollar_volume:,.0f}$) -- محتمل float صغير قابل للانفجار"
                ),
                short_float_pct=short_interest.short_float_pct,
                short_interest_shares=short_interest.short_interest_shares,
                borrow_fee_pct=short_interest.borrow_fee_pct,
                rsi=rsi,
                post_split_rise_pct=rise_pct,
                ema_position=ema_position,
            )
            return None, "low_dollar_volume", near_miss

        # -------- سقف أمان للحالات الشاذة جدًا فقط --------
        if rise_pct > _SANITY_CEILING_RISE_PCT:
            return None, "extreme_rise_sanity_check", None

        detector = SupportDetector()
        support_zone = detector.detect(
            df,
            tolerance_pct=params.support_tolerance_pct,
            min_touches=max(2, params.min_touches - 1),
            min_base_days=params.min_base_days,
        )

        if support_zone is None:
            return None, "no_support_zone_found", None

        if support_zone.touches < params.min_touches:
            short_interest = self.short_interest_source.get_short_interest(ticker)
            near_miss = NearMissResult(
                ticker=ticker,
                price=last_price,
                gap_description=(
                    f"عدد ارتدادات الدعم {support_zone.touches} فقط "
                    f"(المطلوب {params.min_touches})"
                ),
                short_float_pct=short_interest.short_float_pct,
                short_interest_shares=short_interest.short_interest_shares,
                borrow_fee_pct=short_interest.borrow_fee_pct,
                rsi=rsi,
                touches=support_zone.touches,
                base_days=support_zone.base_days,
                post_split_rise_pct=rise_pct,
                stop_loss=support_zone.first_touch_low,
                ema_position=ema_position,
            )
            return None, "not_enough_touches", near_miss

        if support_zone.broken:
            return None, "support_zone_broken", None

        zone_mid = (support_zone.zone_low + support_zone.zone_high) / 2
        distance_from_support_pct = (last_price - zone_mid) / zone_mid * 100
        if distance_from_support_pct > params.max_distance_from_support_pct:
            return None, "too_far_from_support", None

        volume_analyzer = VolumeAnalyzer(rvol_window=RVOL_AVERAGE_WINDOW)
        volume_profile = volume_analyzer.analyze(df, support_zone.base_days)

        if params.exclude_impactful_news:
            news_check = self.news_source.check_impactful_news(ticker, lookback_days=14)
            if news_check.has_impactful_news:
                return None, "impactful_news", None

        short_interest = self.short_interest_source.get_short_interest(ticker)
        if params.max_short_float_pct is not None and short_interest.short_float_pct is not None:
            if short_interest.short_float_pct > params.max_short_float_pct:
                return None, "high_short_float", None

        scorer = PhoenixScorer(tolerance_pct=params.support_tolerance_pct)
        score = scorer.score(reverse_split, support_zone, volume_profile, rise_pct)

        result = StockResult(
            ticker=ticker,
            price=last_price,
            support_zone=support_zone,
            distance_from_support_pct=distance_from_support_pct,
            reverse_split=reverse_split,
            volume_profile=volume_profile,
            short_interest=short_interest,
            score=score,
            rsi=rsi,
            post_split_rise_pct=rise_pct,
            ema_position=ema_position,
        )
        return result, "passed", None
