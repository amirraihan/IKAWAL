"""E6 — Risk scoring: transparent 0-100 priority score with reasons.

Rules-based v1 (works on today's columns). The design keeps nationalities and
ethnicity out of scoring; an ML upgrade is a later wave.
"""

from __future__ import annotations

from typing import Any

from ..constants import (
    RISK_LABEL_CUTOFFS, RISK_SCORE_CAP, RISK_WEIGHTS, STD_REMAN_DAYS,
    TINDAKAN_FINAL, TINDAKAN_PENDING,
)

MODEL_VERSION = "rules-v1"


def label_for(score: int) -> str:
    for cutoff, label in RISK_LABEL_CUTOFFS:
        if score >= cutoff:
            return label
    return "Rendah"


def score_record(record: dict[str, Any], depot_occupancy_pct: float | None = None) -> dict[str, Any]:
    """Compute (score, label, reasons) for a featured case."""
    score = 0
    reasons: list[str] = []

    kod = record.get("tindakan_kod")
    hari = record.get("hari_berbaki")
    not_final = kod not in TINDAKAN_FINAL

    if not_final and hari is not None and hari <= 0:
        score += RISK_WEIGHTS["ends_today_or_overdue"]
        reasons.append("Reman tamat hari ini / tertunggak dan TINDAKAN belum muktamad")
    elif not_final and hari is not None and 1 <= hari <= 3:
        score += RISK_WEIGHTS["ends_in_1_3_days"]
        reasons.append("Reman tamat dalam 1-3 hari")

    if kod == TINDAKAN_PENDING:
        score += RISK_WEIGHTS["tindakan_pending"]
        reasons.append("TINDAKAN belum muktamad (ujian DNA / rayuan / kosong)")

    tempoh = record.get("tempoh_reman")
    if tempoh and tempoh > STD_REMAN_DAYS:
        score += RISK_WEIGHTS["extended_over_14"]
        reasons.append(f"Tempoh reman {tempoh} hari (> {STD_REMAN_DAYS}: kemungkinan lanjutan)")

    if record.get("flag_ulang"):
        score += RISK_WEIGHTS["repeat_case"]
        reasons.append("Kes berulang (tangkap semula / tahan semula)")

    umur = record.get("umur_thn")
    if umur and umur >= 60:
        score += RISK_WEIGHTS["age_60_plus"]
        reasons.append("Umur 60 tahun ke atas (rentan)")

    if not record.get("no_reman") or not record.get("fail"):
        score += RISK_WEIGHTS["admin_gap"]
        reasons.append("Jurang admin: NO.REMAN atau FAIL kosong")

    if depot_occupancy_pct is not None and depot_occupancy_pct >= 0.90:
        score += RISK_WEIGHTS["depot_near_capacity"]
        reasons.append("Depot melebihi 90% kapasiti")

    score = min(score, RISK_SCORE_CAP)
    return {"risk_score": score, "risk_label": label_for(score), "risk_reasons": reasons}


# Fairness guard (design table 5.3): these fields must never be scoring inputs.
FORBIDDEN_INPUTS = ("warganegara", "bangsa", "nama", "dokumen")


def apply_score(record: dict[str, Any], depot_occupancy_pct: float | None = None) -> dict[str, Any]:
    """Score in place and return the record."""
    result = score_record(record, depot_occupancy_pct=depot_occupancy_pct)
    record.update(result)
    return record
