"""Feature layer (E3) — the derived fields of section 2.2.

Every engine (E5-E9) reads features, not raw rows, so the derivation logic lives
in exactly one place.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from ..config import today as _today
from ..constants import STD_REMAN_DAYS, TINDAKAN_FINAL
from ..ingest.cleaning import (
    age_band, classify_akta, classify_tindakan, extract_seksyen, is_repeat,
)

_STATUS_SELESAI = "Selesai"
_STATUS_TERTUNGGAK = "Tertunggak"
_STATUS_DUE_TODAY = "Tamat hari ini"
_STATUS_DUE_SOON = "Tamat <= 3 hari"
_STATUS_AKTIF = "Aktif"
STATUS_ORDER = [_STATUS_TERTUNGGAK, _STATUS_DUE_TODAY, _STATUS_DUE_SOON, _STATUS_AKTIF, _STATUS_SELESAI]


def _as_date(value: Any) -> date | None:
    if value in (None, "", "NaT"):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def compute_features(record: dict[str, Any], as_of: date | None = None) -> dict[str, Any]:
    """Populate the derived fields (section 2.2) on a record, in place."""
    ref = as_of or _today()
    start = _as_date(record.get("tarikh_reman_mula"))
    end = _as_date(record.get("tarikh_reman_tamat"))

    record["tarikh_reman_mula"] = start.isoformat() if start else None
    record["tarikh_reman_tamat"] = end.isoformat() if end else None

    tempoh = (end - start).days + 1 if start and end else None
    record["tempoh_reman"] = tempoh
    hari = (end - ref).days if end else None
    record["hari_berbaki"] = hari

    tindakan_kod = classify_tindakan(record.get("tindakan"))
    record["tindakan_kod"] = tindakan_kod
    record["status_reman"] = _status(hari, tindakan_kod)

    record["akta"] = classify_akta(record.get("kesalahan"))
    record["seksyen"] = extract_seksyen(record.get("kesalahan"))
    record["kumpulan_umur"] = age_band(record.get("umur_thn"))
    record["flag_ulang"] = is_repeat(record.get("catatan"))
    return record


def _status(hari: int | None, tindakan_kod: str) -> str:
    if tindakan_kod in TINDAKAN_FINAL:
        return _STATUS_SELESAI
    if hari is None:
        return _STATUS_AKTIF
    if hari < 0:
        return _STATUS_TERTUNGGAK
    if hari == 0:
        return _STATUS_DUE_TODAY
    if hari <= 3:
        return _STATUS_DUE_SOON
    return _STATUS_AKTIF


def recompute_dataframe(df: pd.DataFrame, as_of: date | None = None) -> pd.DataFrame:
    """Recompute derived fields for a DataFrame of records."""
    if df.empty:
        return df
    ref = as_of or _today()
    rows = [compute_features(dict(r), as_of=ref) for r in df.to_dict("records")]
    return pd.DataFrame(rows)


def daily_counts_per_depot(df: pd.DataFrame, as_of: date | None = None) -> pd.DataFrame:
    """Active caseload per depot on a reference date (feeding UC-3 Stage B)."""
    ref = as_of or _today()
    if df.empty:
        return pd.DataFrame(columns=["depot", "aktif", "kapasiti", "occupancy_pct"])
    work = df.copy()
    work["tarikh_reman_mula"] = pd.to_datetime(work["tarikh_reman_mula"], errors="coerce")
    work["tarikh_reman_tamat"] = pd.to_datetime(work["tarikh_reman_tamat"], errors="coerce")
    ref_ts = pd.Timestamp(ref)
    active = work[(work["tarikh_reman_mula"] <= ref_ts) & (work["tarikh_reman_tamat"] >= ref_ts)]
    counts = active.groupby("depot").size().rename("aktif").reset_index()
    return counts
