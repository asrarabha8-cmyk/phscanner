"""
data_sources/news_source.py
------------------------------
المرحلة 1: فلترة بسيطة بالكلمات المفتاحية على عناوين الأخبار المتاحة عبر
yfinance (Ticker.news). هذا ليس مثاليًا (لا يوجد فهم لغوي حقيقي)، لكنه كافٍ
لاستبعاد الحالات الواضحة (Earnings, FDA, Merger...) دون الحاجة لمفتاح API.

خارطة الطريق للمرحلة 2: استبدال هذا بمصدر أخبار مهيكل (مثل Finnhub News API
أو Benzinga) مع تصنيف فعلي لنوع الخبر بدل مطابقة كلمات.
"""

import logging
from datetime import datetime, timedelta, timezone

from config import IMPACTFUL_NEWS_KEYWORDS
from core.models import NewsCheckResult
from data_sources.base import NewsSource

logger = logging.getLogger(__name__)


class YFinanceKeywordNewsSource(NewsSource):
    def check_impactful_news(self, ticker: str, lookback_days: int) -> NewsCheckResult:
        try:
            import yfinance as yf

            news_items = yf.Ticker(ticker).news or []
            cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

            for item in news_items:
                # بنية yfinance.news قد تتغير بين الإصدارات؛ نتعامل بمرونة
                content = item.get("content", item)
                title = (content.get("title") or "").strip()
                pub_ts = content.get("pubDate") or item.get("providerPublishTime")

                published_at = self._parse_timestamp(pub_ts)
                if published_at is not None and published_at < cutoff:
                    continue

                lowered = title.lower()
                for keyword in IMPACTFUL_NEWS_KEYWORDS:
                    if keyword in lowered:
                        return NewsCheckResult(
                            has_impactful_news=True, matched_headline=title
                        )

            return NewsCheckResult(has_impactful_news=False)
        except Exception as exc:  # noqa: BLE001
            logger.warning("فشل فحص الأخبار لـ %s: %s", ticker, exc)
            # في حال فشل الفحص، لا نستبعد السهم ظلمًا؛ نفترض عدم وجود خبر مؤثر
            return NewsCheckResult(has_impactful_news=False)

    @staticmethod
    def _parse_timestamp(pub_ts):
        if pub_ts is None:
            return None
        try:
            if isinstance(pub_ts, (int, float)):
                return datetime.fromtimestamp(pub_ts, tz=timezone.utc)
            if isinstance(pub_ts, str):
                return datetime.fromisoformat(pub_ts.replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            return None
        return None
