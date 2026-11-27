"""Data-access repository (E2 storage + E10 audit trail).

All reads/writes of the reman table, event log, decision log, forecasts and KPI
snapshots go through :class:`RepanRepository`.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .db import init_db, managed
from .constants import (
    CANONICAL_SOURCE_COLUMNS, DERIVED_COLUMNS, ENGINE_COLUMNS,
)

_META_COLUMNS = ["source", "is_valid", "issues", "created_at", "updated_at"]
_ALL_COLUMNS = CANONICAL_SOURCE_COLUMNS + DERIVED_COLUMNS + ENGINE_COLUMNS + _META_COLUMNS
# Columns that hold JSON-encoded lists.
_JSON_COLUMNS = {"issues", "risk_reasons"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class RepanRepository:
    """Thin, explicit data-access object over the SQLite schema."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = db_path
        init_db(db_path)

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _encode(record: dict[str, Any]) -> dict[str, Any]:
        out = {}
        for key in _ALL_COLUMNS:
            if key not in record:
                continue
            value = record[key]
            if key in _JSON_COLUMNS and not isinstance(value, (str, type(None))):
                value = json.dumps(value, ensure_ascii=False)
            if isinstance(value, bool):
                value = int(value)
            out[key] = value
        return out

    @staticmethod
    def _decode(row: Any) -> dict[str, Any]:
        if row is None:
            return {}
        d = dict(row)
        for key in _JSON_COLUMNS:
            raw = d.get(key)
            if isinstance(raw, str) and raw:
                try:
                    d[key] = json.loads(raw)
                except json.JSONDecodeError:
                    d[key] = raw
        if "flag_ulang" in d:
            d["flag_ulang"] = bool(d["flag_ulang"])
        return d

    # -- writes ------------------------------------------------------------
    def upsert_reman(self, record: dict[str, Any], actor: str = "system",
                     role: str = "officer", source: str = "manual") -> str:
        """Insert or update a reman case; always appends an event-log entry."""
        rec = self._encode(dict(record))
        rec.setdefault("source", source)
        rec["updated_at"] = _now()

        with managed(self.db_path) as conn:
            existing = conn.execute(
                "SELECT no_reman, created_at FROM reman WHERE no_reman = ?",
                (rec["no_reman"],),
            ).fetchone()
            action = "update" if existing else "create"
            if existing:
                rec.setdefault("created_at", existing["created_at"])
                cols = ", ".join(f"{c}=?" for c in rec)
                conn.execute(
                    f"UPDATE reman SET {cols} WHERE no_reman = ?",
                    (*rec.values(), rec["no_reman"]),
                )
            else:
                rec.setdefault("created_at", _now())
                cols = ", ".join(rec.keys())
                placeholders = ", ".join("?" for _ in rec)
                conn.execute(
                    f"INSERT INTO reman ({cols}) VALUES ({placeholders})",
                    tuple(rec.values()),
                )
            conn.execute(
                "INSERT INTO event_log(ts, actor, role, action, no_reman, details) "
                "VALUES (?,?,?,?,?,?)",
                (_now(), actor, role, action, rec["no_reman"],
                 json.dumps({"source": source}, ensure_ascii=False)),
            )
            conn.commit()
        return rec["no_reman"]

    def log_event(self, action: str, no_reman: str | None = None,
                  actor: str = "system", role: str = "officer",
                  details: dict | None = None) -> None:
        with managed(self.db_path) as conn:
            conn.execute(
                "INSERT INTO event_log(ts, actor, role, action, no_reman, details) "
                "VALUES (?,?,?,?,?,?)",
                (_now(), actor, role, action, no_reman,
                 json.dumps(details or {}, ensure_ascii=False)),
            )
            conn.commit()

    def save_risk(self, no_reman: str, score: int, label: str,
                  reasons: list[str], model: str = "rules-v1") -> None:
        with managed(self.db_path) as conn:
            conn.execute(
                "INSERT INTO risk_history(ts, no_reman, score, label, reasons, model) "
                "VALUES (?,?,?,?,?,?)",
                (_now(), no_reman, score, label,
                 json.dumps(reasons, ensure_ascii=False), model),
            )
            conn.commit()

    def save_decision(self, no_reman: str, recommended: str, decision: str,
                      override_action: str | None = None,
                      reason: str | None = None, actor: str = "officer") -> None:
        with managed(self.db_path) as conn:
            conn.execute(
                "INSERT INTO decision_log(ts, no_reman, recommended_action, "
                "officer_decision, override_action, reason, actor) VALUES (?,?,?,?,?,?,?)",
                (_now(), no_reman, recommended, decision, override_action, reason, actor),
            )
            conn.commit()

    def save_forecast(self, run_date: str, depot: str, horizon_date: str,
                      yhat: float, lo: float, hi: float, model: str) -> None:
        with managed(self.db_path) as conn:
            conn.execute(
                "INSERT INTO forecast(run_date, depot, horizon_date, yhat, yhat_lo, "
                "yhat_hi, model) VALUES (?,?,?,?,?,?,?)",
                (run_date, depot, horizon_date, yhat, lo, hi, model),
            )
            conn.commit()

    def save_kpis(self, period: str, kpis: dict[str, float]) -> None:
        with managed(self.db_path) as conn:
            conn.executemany(
                "INSERT INTO kpi_snapshot(ts, period, kpi, value) VALUES (?,?,?,?)",
                [(_now(), period, k, float(v)) for k, v in kpis.items()],
            )
            conn.commit()

    def add_reject(self, source: str, raw: dict, issues: list[str]) -> None:
        with managed(self.db_path) as conn:
            conn.execute(
                "INSERT INTO rejects(ts, source, raw, issues) VALUES (?,?,?,?)",
                (_now(), source, json.dumps(raw, ensure_ascii=False, default=str),
                 json.dumps(issues, ensure_ascii=False)),
            )
            conn.commit()

    # -- reads -------------------------------------------------------------
    def get_reman(self, no_reman: str) -> dict[str, Any]:
        with managed(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM reman WHERE no_reman = ?", (no_reman,)
            ).fetchone()
        return self._decode(row)

    def all_reman(self, include_invalid: bool = True) -> list[dict[str, Any]]:
        sql = "SELECT * FROM reman"
        if not include_invalid:
            sql += " WHERE is_valid = 1"
        with managed(self.db_path) as conn:
            rows = conn.execute(sql).fetchall()
        return [self._decode(r) for r in rows]

    def to_dataframe(self, include_invalid: bool = True) -> pd.DataFrame:
        rows = self.all_reman(include_invalid=include_invalid)
        if not rows:
            return pd.DataFrame(columns=_ALL_COLUMNS)
        return pd.DataFrame(rows)

    def count(self) -> int:
        with managed(self.db_path) as conn:
            return int(conn.execute("SELECT COUNT(*) AS n FROM reman").fetchone()["n"])

    def events(self, limit: int = 200) -> list[dict[str, Any]]:
        with managed(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM event_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def decisions(self, limit: int = 200) -> list[dict[str, Any]]:
        with managed(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM decision_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def latest_forecast(self) -> pd.DataFrame:
        with managed(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM forecast WHERE run_date = "
                "(SELECT MAX(run_date) FROM forecast) ORDER BY depot, horizon_date"
            ).fetchall()
        return pd.DataFrame([dict(r) for r in rows])

    def depot_capacity(self) -> dict[str, int]:
        with managed(self.db_path) as conn:
            rows = conn.execute("SELECT depot, capacity FROM reference_depot").fetchall()
        return {r["depot"]: int(r["capacity"]) for r in rows}

    def rejects_count(self) -> int:
        with managed(self.db_path) as conn:
            return int(conn.execute("SELECT COUNT(*) AS n FROM rejects").fetchone()["n"])
