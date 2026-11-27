"""E8 — Population forecaster (UC-3).

Stage A (runs on today's data): weekly new-reman intake per depot.
Stage B (needs exit dates): headcount = previous headcount + intake - exits.

Models: a moving-average baseline always; SARIMA via statsmodels and a
gradient-boosting model via scikit-learn when the libraries are available. The
best model per depot is chosen by back-test MAPE.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from ..config import get_settings, today as _today

try:  # optional
    from statsmodels.tsa.statespace.sarimax import SARIMAX  # type: ignore

    _HAS_STATSMODELS = True
except Exception:  # pragma: no cover
    _HAS_STATSMODELS = False

try:  # optional
    from sklearn.ensemble import HistGradientBoostingRegressor  # type: ignore

    _HAS_SKLEARN = True
except Exception:  # pragma: no cover
    _HAS_SKLEARN = False


@dataclass
class ForecastResult:
    depot: str
    model: str
    mape: float | None
    horizon: pd.DataFrame  # columns: week_start, yhat, yhat_lo, yhat_hi


# ---------------------------------------------------------------------------
# Stage A — intake
# ---------------------------------------------------------------------------
def weekly_intake(df: pd.DataFrame, depot: str | None = None) -> pd.Series:
    """Weekly count of new reman (by tarikh_reman_mula), indexed by week start."""
    if df.empty or "tarikh_reman_mula" not in df.columns:
        return pd.Series(dtype="float64")
    work = df.copy()
    if depot is not None:
        work = work[work["depot"] == depot]
    work["mula"] = pd.to_datetime(work["tarikh_reman_mula"], errors="coerce")
    work = work.dropna(subset=["mula"])
    if work.empty:
        return pd.Series(dtype="float64")
    weekly = work.groupby(work["mula"].dt.to_period("W-SUN")).size()
    weekly.index = weekly.index.start_time.normalize()  # Monday-anchored
    if not weekly.empty:
        full = pd.date_range(weekly.index.min(), weekly.index.max(), freq="W-MON")
        weekly = weekly.reindex(full, fill_value=0)
    weekly.index.name = "week_start"
    return weekly.astype("float64")


def _ma_forecast(y: np.ndarray, horizon: int, window: int = 4) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    window = min(window, len(y)) if len(y) else 1
    level = float(np.mean(y[-window:])) if len(y) else 0.0
    resid = y[-window:] - level if len(y) else np.array([0.0])
    sd = float(np.std(resid)) if len(resid) else 0.0
    yhat = np.maximum(np.full(horizon, level), 0.0)
    lo = np.maximum(yhat - 1.96 * sd, 0.0)
    hi = yhat + 1.96 * sd
    return yhat, lo, hi


def _sarima_forecast(y: np.ndarray, horizon: int) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    if not _HAS_STATSMODELS or len(y) < 12:
        return None
    try:
        model = SARIMAX(y, order=(1, 1, 1), seasonal_order=(0, 0, 1, 4),
                        enforce_stationarity=False, enforce_invertibility=False)
        fit = model.fit(disp=False)
        fc = fit.get_forecast(steps=horizon)
        mean = np.maximum(np.asarray(fc.predicted_mean), 0.0)
        ci = fc.conf_int(alpha=0.05)
        lo = np.maximum(np.asarray(ci[:, 0]), 0.0)
        hi = np.asarray(ci[:, 1])
        return mean, lo, hi
    except Exception:
        return None


def _gbm_forecast(y: np.ndarray, horizon: int, lags: int = 4) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    if not _HAS_SKLEARN or len(y) < lags + 12:
        return None
    try:
        rows, targets = [], []
        for i in range(lags, len(y)):
            rows.append(list(y[i - lags:i]) + [i])
            targets.append(y[i])
        X, t = np.asarray(rows), np.asarray(targets)
        model = HistGradientBoostingRegressor(max_depth=3, max_iter=200, learning_rate=0.05)
        model.fit(X, t)
        hist = list(y)
        preds = []
        for step in range(horizon):
            row = np.asarray([hist[-lags:] + [len(y) + step]])
            p = float(model.predict(row)[0])
            preds.append(max(p, 0.0))
            hist.append(p)
        preds = np.asarray(preds)
        sd = float(np.std(t - model.predict(X)))
        return preds, np.maximum(preds - 1.96 * sd, 0.0), preds + 1.96 * sd
    except Exception:
        return None


def _backtest_mape(y: np.ndarray, model: str, horizon: int) -> float | None:
    hold = min(horizon, max(len(y) // 4, 1))
    if len(y) - hold < 4:
        return None
    train, test = y[:-hold], y[-hold:]
    if model == "sarima":
        fc = _sarima_forecast(train, len(test))
    elif model == "gbm":
        fc = _gbm_forecast(train, len(test))
    else:
        fc = _ma_forecast(train, len(test))
    if fc is None:
        return None
    yhat = fc[0]
    denom = np.where(test == 0, 1.0, test)
    return float(np.mean(np.abs(yhat - test) / denom))


def forecast_series(series: pd.Series, horizon: int) -> ForecastResult:
    """Forecast one depot's weekly intake and pick the best model by MAPE."""
    depot = str(series.name) if series.name is not None else "ALL"
    y = np.asarray(series.values, dtype="float64")
    candidates: dict[str, tuple] = {"moving_avg": _ma_forecast(y, horizon)}
    sarima = _sarima_forecast(y, horizon)
    if sarima is not None:
        candidates["sarima"] = sarima
    gbm = _gbm_forecast(y, horizon)
    if gbm is not None:
        candidates["gbm"] = gbm

    scored = []
    for name in candidates:
        mape = _backtest_mape(y, name, horizon)
        scored.append((mape if mape is not None else float("inf"), name))
    scored.sort()
    best_mape, best_model = scored[0]
    mean, lo, hi = candidates[best_model]

    last = series.index.max() if len(series) else pd.Timestamp(_today())
    weeks = pd.date_range(last + pd.Timedelta(weeks=1), periods=horizon, freq="W-MON")
    horizon_df = pd.DataFrame({
        "week_start": weeks,
        "yhat": np.round(mean, 1),
        "yhat_lo": np.round(lo, 1),
        "yhat_hi": np.round(hi, 1),
    })
    return ForecastResult(
        depot=depot,
        model=best_model,
        mape=None if best_mape == float("inf") else round(best_mape, 3),
        horizon=horizon_df,
    )


def forecast_all_depots(df: pd.DataFrame, horizon: int | None = None) -> list[ForecastResult]:
    """Stage A forecast for each depot that has history."""
    settings = get_settings()
    horizon = horizon or settings.forecast_horizon_weeks
    results: list[ForecastResult] = []
    depots = sorted(d for d in df.get("depot", pd.Series(dtype=str)).dropna().unique() if d)
    for depot in depots:
        series = weekly_intake(df, depot)
        if len(series) < 2:
            continue
        series.name = depot
        results.append(forecast_series(series, horizon))
    # fleet-wide series
    overall = weekly_intake(df)
    if len(overall) >= 2:
        overall.name = "SEMUA"
        results.append(forecast_series(overall, horizon))
    return results


# ---------------------------------------------------------------------------
# Stage B — headcount (needs exit dates)
# ---------------------------------------------------------------------------
def has_exit_dates(df: pd.DataFrame) -> bool:
    return any(c in df.columns for c in ("tarikh_usir_keluar", "tarikh_keluar", "tarikh_usir"))


def current_headcount(df: pd.DataFrame, as_of: date | None = None) -> dict[str, int]:
    """Active caseload per depot as of a date."""
    ref = pd.Timestamp(as_of or _today())
    if df.empty:
        return {}
    work = df.copy()
    work["mula"] = pd.to_datetime(work["tarikh_reman_mula"], errors="coerce")
    work["tamat"] = pd.to_datetime(work["tarikh_reman_tamat"], errors="coerce")
    active = work[(work["mula"] <= ref) & (work["tamat"] >= ref)]
    return active.groupby("depot").size().to_dict()


def capacity_warnings(df: pd.DataFrame, as_of: date | None = None) -> list[dict[str, Any]]:
    """Depots at or above the capacity-warning threshold."""
    settings = get_settings()
    head = current_headcount(df, as_of=as_of)
    out = []
    for depot, count in head.items():
        cap = settings.depot_capacity.get(depot)
        if not cap:
            continue
        pct = count / cap
        if pct >= settings.capacity_warn_pct:
            out.append({"depot": depot, "headcount": count, "capacity": cap,
                        "occupancy_pct": round(pct, 3)})
    return out
