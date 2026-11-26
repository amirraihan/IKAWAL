"""SQLite persistence for UC-4 monthly report drafts & analyst release state."""

from __future__ import annotations

import datetime as dt
import json
import os
import sqlite3
from typing import Any

from uc4.phase1_kpi.engine import DEFAULT_DB_PATH


def _connect(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    ensure_uc4_table(conn)
    return conn


def ensure_uc4_table(conn: sqlite3.Connection) -> None:
    """Create the uc4_reports table lazily if it does not exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS uc4_reports (
            month TEXT PRIMARY KEY,
            month_label TEXT,
            kpi_json TEXT NOT NULL,
            narrative_text TEXT NOT NULL,
            narrative_mode TEXT,
            provider TEXT,
            numeric_guard_json TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            reviewed_by TEXT DEFAULT '',
            reviewed_at TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def _row_to_report(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "month": row["month"],
        "month_label": row["month_label"],
        "kpi_payload": json.loads(row["kpi_json"]),
        "narrative_text": row["narrative_text"],
        "narrative_mode": row["narrative_mode"],
        "provider": row["provider"],
        "numeric_guard": json.loads(row["numeric_guard_json"] or "{}"),
        "status": row["status"],
        "reviewed_by": row["reviewed_by"] or "",
        "reviewed_at": row["reviewed_at"] or "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_saved_report(month_ym: str, db_path: str | None = None) -> dict[str, Any] | None:
    if not os.path.exists(db_path or DEFAULT_DB_PATH):
        return None
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT * FROM uc4_reports WHERE month = ?", (month_ym,)).fetchone()
        return _row_to_report(row)
    finally:
        conn.close()


def list_saved_statuses(db_path: str | None = None) -> dict[str, dict[str, str]]:
    if not os.path.exists(db_path or DEFAULT_DB_PATH):
        return {}
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT month, status, reviewed_by, reviewed_at, updated_at FROM uc4_reports ORDER BY month"
        ).fetchall()
        return {
            r["month"]: {
                "status": r["status"],
                "reviewed_by": r["reviewed_by"] or "",
                "reviewed_at": r["reviewed_at"] or "",
                "updated_at": r["updated_at"],
            }
            for r in rows
        }
    finally:
        conn.close()


def save_report_draft(
    kpi_payload: dict[str, Any],
    narrative_result: dict[str, Any],
    db_path: str | None = None,
) -> dict[str, Any]:
    """Insert or overwrite a monthly UC-4 draft report."""
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    month_ym = kpi_payload["month"]
    conn = _connect(db_path)
    try:
        existing = conn.execute("SELECT created_at FROM uc4_reports WHERE month = ?", (month_ym,)).fetchone()
        created_at = existing["created_at"] if existing else now
        conn.execute(
            """
            INSERT INTO uc4_reports (
                month, month_label, kpi_json, narrative_text, narrative_mode,
                provider, numeric_guard_json, status, reviewed_by, reviewed_at,
                created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(month) DO UPDATE SET
                month_label=excluded.month_label,
                kpi_json=excluded.kpi_json,
                narrative_text=excluded.narrative_text,
                narrative_mode=excluded.narrative_mode,
                provider=excluded.provider,
                numeric_guard_json=excluded.numeric_guard_json,
                status='draft',
                reviewed_by='',
                reviewed_at='',
                updated_at=excluded.updated_at
            """,
            (
                month_ym,
                kpi_payload["month_label"],
                json.dumps(kpi_payload, ensure_ascii=False),
                narrative_result["narrative_text"],
                narrative_result["mode"],
                narrative_result["provider"],
                json.dumps(narrative_result["numeric_guard"], ensure_ascii=False),
                "draft",
                "",
                "",
                created_at,
                now,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM uc4_reports WHERE month = ?", (month_ym,)).fetchone()
        return _row_to_report(row)  # type: ignore[return-value]
    finally:
        conn.close()


def update_report_narrative(
    month_ym: str,
    narrative_text: str,
    numeric_guard: dict[str, Any],
    db_path: str | None = None,
) -> dict[str, Any] | None:
    """Update analyst-edited narrative text and reset release status to draft."""
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """
            UPDATE uc4_reports
            SET narrative_text = ?,
                narrative_mode = 'analyst_edited',
                numeric_guard_json = ?,
                status = 'draft',
                reviewed_by = '',
                reviewed_at = '',
                updated_at = ?
            WHERE month = ?
            """,
            (narrative_text, json.dumps(numeric_guard, ensure_ascii=False), now, month_ym),
        )
        conn.commit()
        if cur.rowcount == 0:
            return None
        row = conn.execute("SELECT * FROM uc4_reports WHERE month = ?", (month_ym,)).fetchone()
        return _row_to_report(row)
    finally:
        conn.close()


def release_report(
    month_ym: str,
    reviewer_name: str,
    db_path: str | None = None,
) -> dict[str, Any] | None:
    """Mark a monthly report as reviewed & released by an analyst/supervisor."""
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """
            UPDATE uc4_reports
            SET status = 'released',
                reviewed_by = ?,
                reviewed_at = ?,
                updated_at = ?
            WHERE month = ?
            """,
            (reviewer_name, now, now, month_ym),
        )
        conn.commit()
        if cur.rowcount == 0:
            return None
        row = conn.execute("SELECT * FROM uc4_reports WHERE month = ?", (month_ym,)).fetchone()
        return _row_to_report(row)
    finally:
        conn.close()
