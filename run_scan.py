"""
run_scan.py
-------------
نقطة دخول لتشغيل السكانر خارج Streamlit -- يستخدمها GitHub Actions
لتشغيل السكان تلقائيًا يوميًا بدون فتح التطبيق يدويًا.
"""

import logging

from core.models import ScreenerParams
from screener import Screener

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


def main():
    logger.warning("بدء السكان التلقائي المجدول...")
    screener = Screener()
    params = ScreenerParams()
    results, near_misses = screener.run(params)
    logger.warning(
        "انتهى السكان التلقائي: %d نتيجة كاملة، %d سهم قريب من التأهل",
        len(results),
        len(near_misses),
    )


if __name__ == "__main__":
    main()
