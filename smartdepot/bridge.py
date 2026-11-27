"""Bridge between the Flask app's `records` table and the SmartDepot engines.

The Flask app (`app.py`) is the single source of truth (SQLite `ikawal.db`).
This module reads its records, maps the Flask field names to the engine's
canonical schema, and runs the feature layer + engines (E3/E5/E6/E7) in memory.
"""

from __future__ import annotations

import os
import sqlite3
import time
from datetime import date
from pathlib import Path
from typing import Any

from .config import today as _today
from .constants import DEPOTS, DEPOT_DISPLAY, DEPOT_UNKNOWN
from .engines import decision_support, reman_engine, risk_scoring
from .features.derive import compute_features
from .forecast import forecaster
from .ingest.cleaning import clean_row
from .reporting import kpis, report_generator

REPO_ROOT = Path(__file__).resolve().parent.parent

# Forecast results are cached briefly: fitting the models takes a few seconds.
_FORECAST_TTL = 600
_FORECAST_CACHE: dict[Any, tuple[float, list]] = {}

# Flask field -> engine canonical field
FLASK_TO_ENGINE = {
    "nombor_reman": "no_reman",
    "pegawai": "nama_pegawai",
    "jenis_kesalahan": "kesalahan",
    "umur": "umur_thn",
    "nombor_fail": "fail",
    "tarikh_tamat_reman": "tarikh_tamat_reman_raw",
}

# The Flask app maps DIP -> Papar, DIKK -> Kota Kinabalu for display.
DEPOT_FROM_DISPLAY = {
    "DIP": "DIP", "DIKK": "DIKK",
    "PAPAR": "DIP", "KOTA KINABALU": "DIKK", "KK": "DIKK",
}


def default_db_path() -> Path:
    env = os.environ.get("IKAWAL_DB")
    return Path(env) if env else REPO_ROOT / "ikawal.db"


def _int_or_none(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _depot(value: Any) -> str:
    key = str(value or "").strip().upper()
    mapped = DEPOT_FROM_DISPLAY.get(key, key)
    return mapped if mapped in DEPOTS else DEPOT_UNKNOWN


def read_flask_records(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Read every row from the Flask `records` table as plain dicts."""
    path = Path(db_path) if db_path else default_db_path()
    if not path.exists():
        return []
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM records").fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def to_engine_record(row: dict[str, Any]) -> dict[str, Any]:
    """Map one Flask record to the engine's canonical *raw* shape."""
    mapped = {
        "no_reman": row.get("nombor_reman"),
        "nama": row.get("nama"),
        "jantina": row.get("jantina"),
        "umur_thn": row.get("umur"),
        "bangsa": row.get("bangsa"),
        "warganegara": row.get("warganegara"),
        "dokumen": row.get("dokumen"),
        "nama_pegawai": row.get("pegawai"),
        "fail": row.get("nombor_fail"),
        "depot": _depot(row.get("depot")),
        "catatan": row.get("catatan"),
        "tindakan": row.get("tindakan"),
        "kesalahan": row.get("jenis_kesalahan"),
        "tarikh_masuk": row.get("tarikh_masuk"),
        "tarikh_tamat_reman_raw": row.get("tarikh_tamat_reman"),
    }
    return mapped


def enrich(rows: list[dict[str, Any]], as_of: date | None = None) -> list[dict[str, Any]]:
    """Clean + derive features + run engines for a list of Flask records."""
    ref = as_of or _today()
    records: list[dict[str, Any]] = []
    for row in rows:
        raw = to_engine_record(row)
        cleaned, issues = clean_row({
            "no_reman": raw["no_reman"], "tarikh_masuk": raw["tarikh_masuk"],
            "tarikh_tamat_reman_raw": raw["tarikh_tamat_reman_raw"],
            "nama": raw["nama"], "jantina": raw["jantina"],
            "umur_thn": _int_or_none(raw["umur_thn"]), "bangsa": raw["bangsa"],
            "warganegara": raw["warganegara"], "dokumen": raw["dokumen"],
            "nama_pegawai": raw["nama_pegawai"], "fail": raw["fail"],
            "depot": raw["depot"], "catatan": raw["catatan"],
            "tindakan": raw["tindakan"], "kesalahan": raw["kesalahan"],
        })
        cleaned["_issues"] = issues
        cleaned["id"] = row.get("id")
        records.append(cleaned)

    occ = _occupancy(records, ref)
    for rec in records:
        compute_features(rec, as_of=ref)
        risk_scoring.apply_score(rec, depot_occupancy_pct=occ.get(rec.get("depot")))
        view = reman_engine.evaluate(rec, as_of=ref)
        rec["alert_tier"] = view["alert_tier"]
        decision_support.apply_recommendation(rec)
    return records


def _occupancy(records: list[dict[str, Any]], ref: date) -> dict[str, float]:
    from .config import get_settings

    caps = get_settings().depot_capacity
    counts: dict[str, int] = {}
    for rec in records:
        rec2 = compute_features(dict(rec), as_of=ref)
        if rec2.get("status_reman") in {"Aktif", "Tamat <= 3 hari", "Tamat hari ini", "Tertunggak"}:
            counts[rec2.get("depot", "")] = counts.get(rec2.get("depot", ""), 0) + 1
    return {d: counts.get(d, 0) / c for d, c in caps.items() if c}


# ---------------------------------------------------------------------------
# High-level helpers used by the API
# ---------------------------------------------------------------------------
def summary(db_path: str | Path | None = None, as_of: date | None = None) -> dict[str, Any]:
    rows = enrich(read_flask_records(db_path), as_of=as_of)
    ov = kpis.overview_kpis(_frame(rows), as_of=as_of)
    risk = _counts(rows, "risk_label")
    status = _counts(rows, "status_reman")
    return {"count": len(rows), "overview": ov, "by_risk": risk, "by_status": status}


def alerts(db_path: str | Path | None = None, as_of: date | None = None) -> list[dict[str, Any]]:
    rows = enrich(read_flask_records(db_path), as_of=as_of)
    return reman_engine.all_alerts(rows, as_of=as_of)


def worklist(db_path: str | Path | None = None, as_of: date | None = None,
             limit: int = 50) -> list[dict[str, Any]]:
    rows = enrich(read_flask_records(db_path), as_of=as_of)
    ranked = sorted(rows, key=lambda r: (-int(r.get("risk_score") or 0),
                                         r.get("hari_berbaki") if r.get("hari_berbaki") is not None else 999))
    return ranked[:limit]


def forecast(db_path: str | Path | None = None, as_of: date | None = None) -> list[dict[str, Any]]:
    """UC-3 weekly intake forecast per depot (cached: model fits are costly)."""
    key = (str(db_path or default_db_path()), as_of.isoformat() if as_of else "")
    cached = _FORECAST_CACHE.get(key)
    now = time.time()
    if cached and now - cached[0] < _FORECAST_TTL:
        return cached[1]

    rows = enrich(read_flask_records(db_path), as_of=as_of)
    results = forecaster.forecast_all_depots(_frame(rows))
    out = []
    for res in results:
        points = []
        for _, r in res.horizon.iterrows():
            wk = r["week_start"]
            points.append({
                "week": wk.date().isoformat() if hasattr(wk, "date") else str(wk),
                "yhat": round(float(r["yhat"]), 1),
                "lo": round(float(r["yhat_lo"]), 1),
                "hi": round(float(r["yhat_hi"]), 1),
            })
        out.append({"depot": res.depot, "model": res.model, "mape": res.mape, "points": points})

    _FORECAST_CACHE[key] = (now, out)
    return out


def forecast_dashboard(db_path: str | Path | None = None, as_of: date | None = None,
                       history_weeks: int = 26) -> dict[str, Any]:
    """Data for the dedicated UC-3 dashboard: per-depot history + forecast + capacity."""
    key = ("dash3", str(db_path or default_db_path()), as_of.isoformat() if as_of else "")
    cached = _FORECAST_CACHE.get(key)
    now = time.time()
    if cached and now - cached[0] < _FORECAST_TTL:
        return cached[1]

    from .config import get_settings

    rows = enrich(read_flask_records(db_path), as_of=as_of)
    df = _frame(rows)
    depots: list[dict[str, Any]] = []
    for res in forecaster.forecast_all_depots(df):
        hist = forecaster.weekly_intake(df, None if res.depot == "SEMUA" else res.depot)
        hist = hist.tail(history_weeks)
        history = [{"week": idx.date().isoformat(), "n": int(v)} for idx, v in hist.items()]
        points = []
        for _, r in res.horizon.iterrows():
            wk = r["week_start"]
            points.append({
                "week": wk.date().isoformat() if hasattr(wk, "date") else str(wk),
                "yhat": round(float(r["yhat"]), 1),
                "lo": round(float(r["yhat_lo"]), 1),
                "hi": round(float(r["yhat_hi"]), 1),
            })
        depots.append({
            "depot": res.depot,
            "display": DEPOT_DISPLAY.get(res.depot, res.depot),
            "model": res.model,
            "mape": res.mape,
            "history": history,
            "forecast": points,
            "next_week": points[0]["yhat"] if points else None,
            "total_horizon": round(sum(p["yhat"] for p in points), 1) if points else 0,
        })

    head = forecaster.current_headcount(df, as_of=as_of)
    capacity = []
    for depot, cap in get_settings().depot_capacity.items():
        hc = head.get(depot, 0)
        capacity.append({
            "depot": depot, "display": DEPOT_DISPLAY.get(depot, depot),
            "headcount": hc, "capacity": cap,
            "pct": round(hc / cap, 3) if cap else 0,
        })

    payload = {
        "depots": depots,
        "capacity": capacity,
        "warnings": forecaster.capacity_warnings(df, as_of=as_of),
        "total_headcount": int(sum(head.values())),
    }
    _FORECAST_CACHE[key] = (now, payload)
    return payload


def monthly_report(db_path: str | Path | None = None, year: int = 0,
                   month: int = 0) -> dict[str, Any]:
    from .config import get_settings

    rows = enrich(read_flask_records(db_path))
    df = _frame(rows)
    out_dir = get_settings().output_dir / "laporan"
    art = report_generator.generate_monthly_report(df, year or _today().year,
                                                   month or _today().month, out_dir)
    return {"period": art["period"], "narrative": art["narrative"],
            "xlsx": str(art["xlsx"]), "docx": str(art["docx"]), "html": str(art["html"]),
            "pdf": str(art["pdf"]) if art.get("pdf") else None}


def _frame(rows: list[dict[str, Any]]):
    import pandas as pd

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _counts(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        k = str(r.get(key) or "-")
        out[k] = out.get(k, 0) + 1
    return out


# ---------------------------------------------------------------------------
# Bundle for the dashboard: per-record engine fields + a panel payload
# ---------------------------------------------------------------------------
_ENGINE_FIELDS = (
    "risk_score", "risk_label", "risk_reasons", "alert_tier", "recommended_action",
    "hari_berbaki", "status_reman", "tempoh_reman", "akta", "seksyen", "tindakan_kod",
)


def engine_bundle(rows: list[dict[str, Any]], as_of: date | None = None) -> dict[str, Any]:
    """Return {by_id, panel} for embedding the engines in the main dashboard."""
    ref = as_of or _today()
    enriched = enrich(rows, as_of=ref)

    by_id: dict[str, dict[str, Any]] = {}
    for rec in enriched:
        rid = rec.get("id")
        if rid:
            # JSON-safe: drop the internal issue list
            by_id[rid] = {k: rec.get(k) for k in _ENGINE_FIELDS}

    alerts = reman_engine.all_alerts(enriched, as_of=ref)
    by_risk = _counts(enriched, "risk_label")
    panel = {
        "by_risk": by_risk,
        "alert_count": len(alerts),
        "critical": by_risk.get("Kritikal", 0),
        "high": by_risk.get("Tinggi", 0),
        "alerts": [
            {
                "id": a.get("id"), "no_reman": a.get("no_reman"), "nama": a.get("nama"),
                "depot": a.get("depot"), "warganegara": a.get("warganegara"),
                "tier": a.get("alert_tier"), "hari_berbaki": a.get("hari_berbaki"),
                "risk_label": a.get("risk_label"), "action": a.get("recommended_action"),
            }
            for a in alerts[:50]
        ],
    }
    return {"by_id": by_id, "panel": panel}
