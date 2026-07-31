"""
data_sources/short_interest_source.py
----------------------------------------
Short Float% : لا يوجد مصدر مجاني موثوق يعطي هذه النسبة لحظيًا لكل الأسهم.
              هذه المرحلة (1) تترك القيمة None ويُعامَل فلتر Short Float
              على أنه "غير مُفعَّل تلقائيًا" حتى يوفّر المستخدم مفتاح API
              لمزود مثل Fintel أو Ortex (راجع config.FINTEL_API_KEY).

Borrow Fee%  : نستخدم iBorrowDesk (مجاني، بدون مفتاح) الذي يجمّع بيانات
              Borrow Fee من عدة وسطاء (بشكل غير رسمي لكنه مستخدم بشكل واسع
              من مجتمع المتداولين).

هذا الملف مصمم بحيث لا يفشل السكرينر بالكامل إذا تعذّر الوصول لأي مصدر:
سيُعاد ShortInterestInfo(available=False) وتتعامل طبقة التسجيل (scorer)
مع ذلك بإعطاء 0 لهذا المكوّن بدل توقف البرنامج.
"""

import logging

import requests

from config import IBORROWDESK_BASE_URL, FINTEL_API_KEY
from core.models import ShortInterestInfo
from data_sources.base import ShortInterestSource

logger = logging.getLogger(__name__)


class CompositeShortInterestSource(ShortInterestSource):
    def get_short_interest(self, ticker: str) -> ShortInterestInfo:
        borrow_fee = self._get_borrow_fee(ticker)
        short_float = self._get_short_float(ticker)

        available = borrow_fee is not None or short_float is not None
        return ShortInterestInfo(
            short_float_pct=short_float,
            borrow_fee_pct=borrow_fee,
            available=available,
        )

    def _get_borrow_fee(self, ticker: str):
        try:
            resp = requests.get(f"{IBORROWDESK_BASE_URL}/{ticker}", timeout=10)
            if resp.status_code != 200:
                return None
            data = resp.json()
            daily = data.get("daily")
            if not daily:
                return None
            latest = daily[-1]
            return float(latest.get("fee"))
        except Exception as exc:  # noqa: BLE001
            logger.debug("لا تتوفر بيانات Borrow Fee لـ %s: %s", ticker, exc)
            return None

    def _get_short_float(self, ticker: str):
        if not FINTEL_API_KEY:
            # المرحلة 2: استبدال هذا باستدعاء فعلي لـ Fintel/Ortex عند توفر مفتاح
            return None
        try:
            # نقطة تمديد جاهزة للمرحلة القادمة — لم يتم تفعيلها لعدم توفر مفتاح افتراضي
            return None
        except Exception as exc:  # noqa: BLE001
            logger.debug("لا تتوفر بيانات Short Float لـ %s: %s", ticker, exc)
            return None
