"""Database layer (E2): connection handling and schema.

Uses the Python standard-library ``sqlite3`` so the pilot runs with zero external
services. The SQL is deliberately plain ANSI-ish SQL so it can be ported to
PostgreSQL (L5 production option) by swapping the connection factory.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import get_settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reman (
    no_reman             TEXT PRIMARY KEY,
    tarikh_masuk         TEXT,
    nama                 TEXT,
    jantina              TEXT,
    umur_thn             INTEGER,
    bangsa               TEXT,
    warganegara          TEXT,
    dokumen              TEXT,
    nama_pegawai         TEXT,
    fail                 TEXT,
    depot                TEXT,
    catatan              TEXT,
    tindakan             TEXT,
    kesalahan            TEXT,
    tarikh_tamat_reman_raw TEXT,
    -- derived feature layer (E3) --
    tarikh_reman_mula    TEXT,
    tarikh_reman_tamat   TEXT,
    tempoh_reman         INTEGER,
    hari_berbaki         INTEGER,
    status_reman         TEXT,
    akta                 TEXT,
    seksyen              TEXT,
    tindakan_kod         TEXT,
    kumpulan_umur        TEXT,
    flag_ulang           INTEGER DEFAULT 0,
    -- engine outputs (E5/E6/E7) --
    risk_score           INTEGER DEFAULT 0,
    risk_label           TEXT,
    risk_reasons         TEXT,
    alert_tier           TEXT,
    recommended_action   TEXT,
    -- meta --
    source               TEXT DEFAULT 'manual',
    is_valid             INTEGER DEFAULT 1,
    issues               TEXT,
    created_at           TEXT,
    updated_at           TEXT
);

CREATE TABLE IF NOT EXISTS event_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    actor       TEXT,
    role        TEXT,
    action      TEXT NOT NULL,
    no_reman    TEXT,
    details     TEXT
);

CREATE TABLE IF NOT EXISTS risk_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    no_reman    TEXT NOT NULL,
    score       INTEGER,
    label       TEXT,
    reasons     TEXT,
    model       TEXT DEFAULT 'rules-v1'
);

CREATE TABLE IF NOT EXISTS decision_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                  TEXT NOT NULL,
    no_reman            TEXT NOT NULL,
    recommended_action  TEXT,
    officer_decision    TEXT,          -- Accept | Override
    override_action     TEXT,
    reason              TEXT,
    actor               TEXT
);

CREATE TABLE IF NOT EXISTS forecast (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date     TEXT NOT NULL,
    depot        TEXT NOT NULL,
    horizon_date TEXT,
    yhat         REAL,
    yhat_lo      REAL,
    yhat_hi      REAL,
    model        TEXT
);

CREATE TABLE IF NOT EXISTS kpi_snapshot (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       TEXT NOT NULL,
    period   TEXT NOT NULL,
    kpi      TEXT NOT NULL,
    value    REAL
);

CREATE TABLE IF NOT EXISTS rejects (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT NOT NULL,
    source     TEXT,
    raw        TEXT,
    issues     TEXT
);

CREATE TABLE IF NOT EXISTS reference_depot (
    depot      TEXT PRIMARY KEY,
    capacity   INTEGER
);

CREATE INDEX IF NOT EXISTS idx_reman_depot   ON reman(depot);
CREATE INDEX IF NOT EXISTS idx_reman_status  ON reman(status_reman);
CREATE INDEX IF NOT EXISTS idx_event_reman   ON event_log(no_reman);
"""


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection with sensible pragmas and dict-like rows."""
    path = Path(db_path) if db_path else get_settings().db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db(db_path: Path | str | None = None) -> None:
    """Create the schema if it does not exist and seed reference data."""
    with managed(db_path) as conn:
        conn.executescript(_SCHEMA)
        settings = get_settings()
        conn.executemany(
            "INSERT OR REPLACE INTO reference_depot(depot, capacity) VALUES (?, ?)",
            list(settings.depot_capacity.items()),
        )


@contextmanager
def managed(db_path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    """Open a connection, commit on success, and always close it.

    ``sqlite3.Connection`` used as a context manager commits but does *not*
    close, which leaves the file locked on Windows. This wrapper closes.
    """
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def session(db_path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    """Alias of :func:`managed` (transactional context manager)."""
    with managed(db_path) as conn:
        yield conn
