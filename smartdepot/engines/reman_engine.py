"""E5 — Reman engine: countdown, alert tiers, draft paperwork context."""

from __future__ import annotations

from datetime import date
from typing import Any

from ..config import get_settings, today as _today
from ..constants import STD_REMAN_DAYS, TINDAKAN_FINAL

# Alert tiers, most urgent first.
TIER_OVERDUE = "overdue"
TIER_DUE_TODAY = "due_today"
TIER_1_DAY = "d1"
TIER_3_DAYS = "d3"
TIER_NONE = "none"

_TIER_ORDER = [TIER_OVERDUE, TIER_DUE_TODAY, TIER_1_DAY, TIER_3_DAYS, TIER_NONE]


def alert_tier(hari_berbaki: int | None, tindakan_kod: str | None,
               as_of: date | None = None) -> str:
    """Alert tier for a case; resolved cases never alert."""
    if tindakan_kod in TINDAKAN_FINAL:
        return TIER_NONE
    if hari_berbaki is None:
        return TIER_NONE
    if hari_berbaki < 0:
        return TIER_OVERDUE
    if hari_berbaki == 0:
        return TIER_DUE_TODAY
    tiers = get_settings().alert_tiers_days
    if 1 in tiers and hari_berbaki == 1:
        return TIER_1_DAY
    if 3 in tiers and hari_berbaki <= 3:
        return TIER_3_DAYS
    return TIER_NONE


def tier_rank(tier: str) -> int:
    return _TIER_ORDER.index(tier) if tier in _TIER_ORDER else len(_TIER_ORDER)


def should_alert(tier: str) -> bool:
    return tier in {TIER_OVERDUE, TIER_DUE_TODAY, TIER_1_DAY, TIER_3_DAYS}


def countdown_text(hari_berbaki: int | None) -> str:
    if hari_berbaki is None:
        return "tiada tarikh tamat"
    if hari_berbaki < 0:
        return f"tertunggak {abs(hari_berbaki)} hari"
    if hari_berbaki == 0:
        return "tamat hari ini"
    return f"{hari_berbaki} hari berbaki"


def evaluate(record: dict[str, Any], as_of: date | None = None) -> dict[str, Any]:
    """Return the reman-engine view of a case."""
    ref = as_of or _today()
    hari = record.get("hari_berbaki")
    if hari is None and record.get("tarikh_reman_tamat"):
        try:
            hari = (date.fromisoformat(str(record["tarikh_reman_tamat"])[:10]) - ref).days
        except ValueError:
            hari = None
    tier = alert_tier(hari, record.get("tindakan_kod"))
    return {
        "hari_berbaki": hari,
        "alert_tier": tier,
        "alert": should_alert(tier),
        "countdown": countdown_text(hari),
        "status_reman": record.get("status_reman"),
        "extension_likely": bool(record.get("tempoh_reman") and record["tempoh_reman"] > STD_REMAN_DAYS),
    }


def build_draft_context(record: dict[str, Any], as_of: date | None = None) -> dict[str, Any]:
    """Context for pre-filled extension / outcome paperwork (see reporting.drafts)."""
    ref = as_of or _today()
    return {
        "no_reman": record.get("no_reman"),
        "nama": record.get("nama"),
        "warganegara": record.get("warganegara"),
        "depot": record.get("depot"),
        "nama_pegawai": record.get("nama_pegawai"),
        "seksyen": record.get("seksyen"),
        "akta": record.get("akta"),
        "tarikh_reman_mula": record.get("tarikh_reman_mula"),
        "tarikh_reman_tamat": record.get("tarikh_reman_tamat"),
        "tempoh_reman": record.get("tempoh_reman"),
        "hari_berbaki": record.get("hari_berbaki"),
        "tindakan_kod": record.get("tindakan_kod"),
        "disediakan_pada": ref.isoformat(),
    }


def all_alerts(records: list[dict[str, Any]], as_of: date | None = None) -> list[dict[str, Any]]:
    """Cases that currently raise an alert, most urgent first."""
    out = []
    for rec in records:
        if not rec.get("tindakan_kod"):  # not yet featured
            continue
        info = evaluate(rec, as_of=as_of)
        if info["alert"]:
            out.append({**rec, **info})
    out.sort(key=lambda r: tier_rank(r["alert_tier"]))
    return out
