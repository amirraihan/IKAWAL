"""KPI rules (E9).

All numbers shown in the monthly report and given to the LLM are computed here,
from the (masked) reman table only — the narrative never invents values.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from ..config import today as _today
from ..features.derive import STATUS_ORDER
from ..constants import TINDAKAN_PENDING


def _to_dt(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_datetime(df[col], errors="coerce") if col in df.columns else pd.Series(pd.NaT, index=df.index)


def overview_kpis(df: pd.DataFrame, as_of: date | None = None) -> dict[str, float]:
    """Headline KPI tiles for the Ringkasan page."""
    ref = pd.Timestamp(as_of or _today())
    if df.empty:
        return {k: 0 for k in (
            "jumlah_reman", "reman_aktif", "tamat_3_hari", "tertunggak",
            "pct_usir", "pct_bebas", "kes_belum_muktamad")}
    mula, tamat = _to_dt(df, "tarikh_reman_mula"), _to_dt(df, "tarikh_reman_tamat")
    active = ((mula <= ref) & (tamat >= ref)).sum()
    terc = df["status_reman"].eq("Tertunggak").sum() if "status_reman" in df else 0
    soon = df["status_reman"].eq("Tamat <= 3 hari").sum() if "status_reman" in df else 0
    total = len(df)
    usir = df["tindakan_kod"].astype(str).str.startswith("USIR").sum() if "tindakan_kod" in df else 0
    bebas = df["tindakan_kod"].eq("BEBAS DENGAN AMARAN").sum() if "tindakan_kod" in df else 0
    pending = df["tindakan_kod"].eq(TINDAKAN_PENDING).sum() if "tindakan_kod" in df else 0
    return {
        "jumlah_reman": int(total),
        "reman_aktif": int(active),
        "tamat_3_hari": int(soon),
        "tertunggak": int(terc),
        "pct_usir": round(100 * usir / total, 1) if total else 0.0,
        "pct_bebas": round(100 * bebas / total, 1) if total else 0.0,
        "kes_belum_muktamad": int(pending),
    }


def _value_counts(df: pd.DataFrame, col: str) -> pd.DataFrame:
    if col not in df.columns:
        return pd.DataFrame(columns=[col, "bilangan", "peratus"])
    vc = df[col].fillna("-").value_counts()
    out = vc.rename_axis(col).reset_index(name="bilangan")
    out["peratus"] = (100 * out["bilangan"] / max(len(df), 1)).round(1)
    return out


def breakdowns(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """The breakdown tables behind dashboard pages 3-5 and the report."""
    return {
        "depot": _value_counts(df, "depot"),
        "warganegara": _value_counts(df, "warganegara"),
        "bangsa": _value_counts(df, "bangsa"),
        "akta": _value_counts(df, "akta"),
        "seksyen": _value_counts(df, "seksyen").head(10),
        "tindakan": _value_counts(df, "tindakan_kod"),
        "jantina": _value_counts(df, "jantina"),
        "kumpulan_umur": _value_counts(df, "kumpulan_umur"),
        "status_reman": _value_counts(df, "status_reman"),
    }


def status_counts(df: pd.DataFrame) -> pd.DataFrame:
    counts = _value_counts(df, "status_reman")
    if counts.empty:
        return counts
    order = {s: i for i, s in enumerate(STATUS_ORDER)}
    counts["_o"] = counts["status_reman"].map(order).fillna(99)
    return counts.sort_values("_o").drop(columns="_o").reset_index(drop=True)


def monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Reman opened per month (for the trend chart and report appendix)."""
    if df.empty:
        return pd.DataFrame(columns=["bulan", "bilangan"])
    mula = _to_dt(df, "tarikh_reman_mula")
    work = pd.DataFrame({"bulan": mula.dt.to_period("M").astype(str)}).dropna()
    return work.groupby("bulan").size().reset_index(name="bilangan")


def filter_period(df: pd.DataFrame, year: int, month: int) -> pd.DataFrame:
    """Rows whose reman started in the given calendar month."""
    if df.empty:
        return df
    mula = _to_dt(df, "tarikh_reman_mula")
    mask = (mula.dt.year == year) & (mula.dt.month == month)
    return df[mask]


def kpi_snapshot(df: pd.DataFrame, year: int, month: int,
                 as_of: date | None = None) -> dict[str, Any]:
    """Everything the report generator needs for one month."""
    period = f"{year:04d}-{month:02d}"
    month_df = filter_period(df, year, month)
    prev_month = month - 1 or 12
    prev_year = year if month > 1 else year - 1
    prev_df = filter_period(df, prev_year, prev_month)

    overview = overview_kpis(month_df, as_of=as_of)
    previous = overview_kpis(prev_df, as_of=as_of)
    change = {k: round(overview[k] - previous.get(k, 0), 1) for k in overview}
    return {
        "period": period,
        "overview": overview,
        "previous": previous,
        "change": change,
        "breakdowns": breakdowns(month_df),
        "monthly_trend": monthly_summary(df),
        "total_in_month": int(len(month_df)),
    }
