"""
data_sources/github_storage.py
---------------------------------
يقرأ ويكتب ملف تتبّع الأسهم (tracked_stocks.csv) مباشرة على GitHub عبر
GitHub REST API، باستخدام GITHUB_TOKEN المخزّن بـ Streamlit secrets.
هذا يضمن أن السجل يبقى دائمًا بين كل إعادة نشر للتطبيق (مو ذاكرة مؤقتة).

هذا الملف نفسه يُقرأ مباشرة (raw) من صفحة المراقبة الثابتة (monitor.html)
المستضافة على GitHub Pages -- المستودع عام، فما يحتاج مصادقة للقراءة.
"""

import base64
import csv
import io
import logging
from datetime import date
from typing import List, Optional

import requests
import streamlit as st

from core.models import TrackedStock

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
REPO_OWNER = "asrarabha8-cmyk"
REPO_NAME = "phscanner"
FILE_PATH = "data/tracked_stocks.csv"

_CSV_HEADERS = [
    "ticker",
    "discovery_date",
    "discovery_price",
    "kind",
    "reason",
    "last_checked_date",
    "last_price",
    "touches",
    "base_days",
    "rsi",
    "short_interest_shares",
    "post_split_rise_pct",
    "stop_loss",
    "phoenix_score",
    "ema_position",
    "cycle_stage",
    "cycle_stage_label",
]


def _headers():
    token = st.secrets["GITHUB_TOKEN"]
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }


def _api_url():
    return f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"


def _parse_optional_float(raw: Optional[str]) -> Optional[float]:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _parse_optional_int(raw: Optional[str]) -> Optional[int]:
    val = _parse_optional_float(raw)
    return int(val) if val is not None else None


def _parse_optional_str(raw: Optional[str]) -> Optional[str]:
    if raw is None or raw == "":
        return None
    return raw


def read_tracked_stocks() -> List[TrackedStock]:
    """يقرأ الملف الحالي من GitHub. يرجع قائمة فاضية لو الملف مو موجود بعد."""
    try:
        resp = requests.get(_api_url(), headers=_headers(), timeout=15)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        content_b64 = resp.json()["content"]
        content = base64.b64decode(content_b64).decode("utf-8")

        reader = csv.DictReader(io.StringIO(content))
        stocks = []
        for row in reader:
            stocks.append(
                TrackedStock(
                    ticker=row["ticker"],
                    discovery_date=date.fromisoformat(row["discovery_date"]),
                    discovery_price=float(row["discovery_price"]),
                    kind=row["kind"],
                    reason=row["reason"],
                    last_checked_date=(
                        date.fromisoformat(row["last_checked_date"])
                        if row.get("last_checked_date")
                        else None
                    ),
                    last_price=(
                        float(row["last_price"]) if row.get("last_price") else None
                    ),
                    touches=_parse_optional_int(row.get("touches")),
                    base_days=_parse_optional_int(row.get("base_days")),
                    rsi=_parse_optional_float(row.get("rsi")),
                    short_interest_shares=_parse_optional_float(
                        row.get("short_interest_shares")
                    ),
                    post_split_rise_pct=_parse_optional_float(
                        row.get("post_split_rise_pct")
                    ),
                    stop_loss=_parse_optional_float(row.get("stop_loss")),
                    phoenix_score=_parse_optional_float(row.get("phoenix_score")),
                    ema_position=_parse_optional_str(row.get("ema_position")),
                    cycle_stage=_parse_optional_int(row.get("cycle_stage")),
                    cycle_stage_label=_parse_optional_str(row.get("cycle_stage_label")),
                )
            )
        return stocks
    except Exception as exc:  # noqa: BLE001
        logger.warning("فشل قراءة ملف tracked_stocks من GitHub: %s", exc)
        return []


def write_tracked_stocks(stocks: List[TrackedStock], commit_message: str) -> bool:
    """يكتب القائمة كاملة إلى الملف على GitHub (استبدال كامل، مو إضافة)."""
    try:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=_CSV_HEADERS)
        writer.writeheader()
        for s in stocks:
            writer.writerow(
                {
                    "ticker": s.ticker,
                    "discovery_date": s.discovery_date.isoformat(),
                    "discovery_price": s.discovery_price,
                    "kind": s.kind,
                    "reason": s.reason,
                    "last_checked_date": s.last_checked_date.isoformat()
                    if s.last_checked_date
                    else "",
                    "last_price": s.last_price if s.last_price is not None else "",
                    "touches": s.touches if s.touches is not None else "",
                    "base_days": s.base_days if s.base_days is not None else "",
                    "rsi": s.rsi if s.rsi is not None else "",
                    "short_interest_shares": (
                        s.short_interest_shares
                        if s.short_interest_shares is not None
                        else ""
                    ),
                    "post_split_rise_pct": (
                        s.post_split_rise_pct if s.post_split_rise_pct is not None else ""
                    ),
                    "stop_loss": s.stop_loss if s.stop_loss is not None else "",
                    "phoenix_score": s.phoenix_score if s.phoenix_score is not None else "",
                    "ema_position": s.ema_position if s.ema_position is not None else "",
                    "cycle_stage": s.cycle_stage if s.cycle_stage is not None else "",
                    "cycle_stage_label": (
                        s.cycle_stage_label if s.cycle_stage_label is not None else ""
                    ),
                }
            )
        content = output.getvalue()
        content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        # نحتاج sha الملف الحالي لو موجود (GitHub يطلبه عند التحديث)
        sha = None
        resp = requests.get(_api_url(), headers=_headers(), timeout=15)
        if resp.status_code == 200:
            sha = resp.json()["sha"]

        payload = {
            "message": commit_message,
            "content": content_b64,
        }
        if sha:
            payload["sha"] = sha

        put_resp = requests.put(_api_url(), headers=_headers(), json=payload, timeout=15)
        put_resp.raise_for_status()
        return True

    except Exception as exc:  # noqa: BLE001
        logger.error("فشل كتابة ملف tracked_stocks إلى GitHub: %s", exc)
        return False


def add_new_tracked_stocks(new_stocks: List[TrackedStock]) -> None:
    """
    يضيف أسهم جديدة للسجل، متجنبًا التكرار (نفس الرمز + نفس تاريخ الاكتشاف).
    يستدعى بعد كل تشغيلة سكانر.
    """
    existing = read_tracked_stocks()
    existing_keys = {(s.ticker, s.discovery_date) for s in existing}

    additions = [
        s for s in new_stocks if (s.ticker, s.discovery_date) not in existing_keys
    ]
    if not additions:
        return

    combined = existing + additions
    success = write_tracked_stocks(
        combined, f"Add {len(additions)} tracked stock(s) from scan"
    )
    if success:
        logger.warning("تم إضافة %d سهم جديد لسجل المتابعة", len(additions))
    else:
        logger.warning("فشل حفظ الأسهم الجديدة بسجل المتابعة")
