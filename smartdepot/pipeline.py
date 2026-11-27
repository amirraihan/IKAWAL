"""End-to-end pipeline orchestration (stages 1-6).

Triggers
--------
on save / upload : capture -> validate/clean -> log/derive -> decide(UC-1/UC-2)
daily 07:00      : UC-2 alerts + UC-3 forecast
monthly (1st)    : UC-4 report
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from .config import get_settings, today as _today
from .constants import CANONICAL_SOURCE_COLUMNS, DEPOTS
from .engines import decision_support, reman_engine, risk_scoring
from .features.derive import compute_features, recompute_dataframe
from .forecast import forecaster
from .ingest.validation import split_issues
from .reporting import report_generator
from .repository import RepanRepository


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def compute_depot_occupancy(repo: RepanRepository, as_of: date | None = None) -> dict[str, float]:
    """Active caseload / capacity per depot (feeds the +5 capacity risk factor)."""
    df = repo.to_dataframe()
    if df.empty:
        return {}
    head = forecaster.current_headcount(df, as_of=as_of)
    caps = get_settings().depot_capacity
    return {d: (head.get(d, 0) / c) for d, c in caps.items() if c}


# ---------------------------------------------------------------------------
# On-save / on-upload (UC-1 + UC-2)
# ---------------------------------------------------------------------------
def process_record(record: dict[str, Any], repo: RepanRepository,
                   actor: str = "system", role: str = "officer",
                   source: str = "manual",
                   extra_issues: list[dict[str, str]] | None = None,
                   as_of: date | None = None,
                   depot_occupancy: dict[str, float] | None = None) -> dict[str, Any]:
    """Run the per-case chain (E3 -> E5 -> E6 -> E7) and store the case."""
    issues = list(extra_issues or [])
    ref = as_of or _today()

    # stage 3 — log & derive (feature layer, E3)
    compute_features(record, as_of=ref)

    # stage 4 — decide: E6 risk (needs depot occupancy), then E5 alert, then E7 action
    occ = depot_occupancy if depot_occupancy is not None else compute_depot_occupancy(repo, as_of=ref)
    pct = occ.get(record.get("depot"))
    risk_scoring.apply_score(record, depot_occupancy_pct=pct)

    engine_view = reman_engine.evaluate(record, as_of=ref)
    record["alert_tier"] = engine_view["alert_tier"]
    record["hari_berbaki"] = engine_view["hari_berbaki"]

    decision_support.apply_recommendation(record)

    # stage 5 — guard: valid only when there are no hard issues
    hard, soft = split_issues(issues)
    record["is_valid"] = 0 if hard else 1
    record["issues"] = issues

    # stage 6 — deliver: persist + audit + alert
    repo.upsert_reman(record, actor=actor, role=role, source=source)
    repo.save_risk(record["no_reman"], record["risk_score"],
                   record["risk_label"], record.get("risk_reasons", []),
                   model=risk_scoring.MODEL_VERSION)
    if reman_engine.should_alert(record["alert_tier"]):
        repo.log_event("alert", no_reman=record["no_reman"], actor="system",
                       details={"tier": record["alert_tier"],
                                "pegawai": record.get("nama_pegawai", ""),
                                "countdown": engine_view["countdown"]})
    return record


# ---------------------------------------------------------------------------
# Daily job (UC-2 alerts + UC-3 forecast)
# ---------------------------------------------------------------------------
def run_daily(repo: RepanRepository, as_of: date | None = None) -> dict[str, Any]:
    """Recompute features/engines for every case, refresh alerts and forecast."""
    ref = as_of or _today()
    df = repo.to_dataframe()
    if df.empty:
        repo.log_event("daily_run", details={"note": "no data", "as_of": ref.isoformat()})
        return {"as_of": ref.isoformat(), "alerts": 0, "forecast": 0}

    # recompute per case and persist refreshed engine outputs
    refreshed = []
    occ = compute_depot_occupancy(repo, as_of=ref)
    for r in df.to_dict("records"):
        r.pop("issues", None)
        refreshed.append(compute_features(r, as_of=ref))
    feat_df = pd.DataFrame(refreshed)

    for r in feat_df.to_dict("records"):
        risk_scoring.apply_score(r, depot_occupancy_pct=occ.get(r.get("depot")))
        view = reman_engine.evaluate(r, as_of=ref)
        r["alert_tier"] = view["alert_tier"]
        decision_support.apply_recommendation(r)
        repo.upsert_reman(r, actor="system", role="officer", source="daily")

    alerts = reman_engine.all_alerts(feat_df.to_dict("records"), as_of=ref)

    results = forecaster.forecast_all_depots(feat_df)
    for res in results:
        for _, row in res.horizon.iterrows():
            repo.save_forecast(ref.isoformat(), res.depot,
                               str(row["week_start"].date()), float(row["yhat"]),
                               float(row["yhat_lo"]), float(row["yhat_hi"]), res.model)

    warnings = forecaster.capacity_warnings(feat_df, as_of=ref)
    repo.log_event("daily_run", actor="system",
                   details={"as_of": ref.isoformat(), "alerts": len(alerts),
                            "forecast_depots": len(results),
                            "capacity_warnings": len(warnings)})
    return {"as_of": ref.isoformat(), "alerts": len(alerts),
            "forecast": len(results), "capacity_warnings": warnings,
            "alert_list": alerts, "forecast_results": results}


# ---------------------------------------------------------------------------
# Monthly job (UC-4 report)
# ---------------------------------------------------------------------------
def run_monthly(repo: RepanRepository, year: int, month: int) -> dict[str, Any]:
    """Generate the monthly report and snapshot the KPIs."""
    df = repo.to_dataframe()
    out_dir = get_settings().output_dir / "laporan"
    artifacts = report_generator.generate_monthly_report(df, year, month, out_dir)
    repo.save_kpis(artifacts["period"], artifacts["snapshot"]["overview"])
    repo.log_event("monthly_run", actor="system",
                   details={"period": artifacts["period"],
                            "xlsx": str(artifacts["xlsx"])})
    return artifacts


def run_all(repo: RepanRepository, as_of: date | None = None) -> dict[str, Any]:
    """Convenience: recompute everything (used by scripts and tests)."""
    return run_daily(repo, as_of=as_of)
