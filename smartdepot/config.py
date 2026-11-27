"""Runtime configuration: paths, database location, tunable thresholds.

Values can be overridden with environment variables so the same code runs in a
pilot (SQLite, local files) or a production deployment (e.g. PostgreSQL) without
editing source.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

# Package lives at <repo_root>/smartdepot/, so the repo root is one level up.
REPO_ROOT = Path(__file__).resolve().parent.parent


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser().resolve() if raw else default


@dataclass(frozen=True)
class Settings:
    """Immutable settings object."""

    repo_root: Path = REPO_ROOT
    data_dir: Path = field(default_factory=lambda: _env_path("SMARTDEPOT_DATA_DIR", REPO_ROOT / "data"))
    output_dir: Path = field(default_factory=lambda: _env_path("SMARTDEPOT_OUTPUT_DIR", REPO_ROOT / "outputs"))
    db_path: Path = field(
        default_factory=lambda: _env_path("SMARTDEPOT_DB", REPO_ROOT / "data" / "smartdepot.db")
    )

    # Reference "today" for demos/tests. None => use the real current date.
    as_of: date | None = None

    # Depot capacities (reference table). Open question #5 in the design doc.
    depot_capacity: dict = field(default_factory=lambda: {"DIKK": 1500, "DIP": 1200})
    capacity_warn_pct: float = 0.90  # UC-3 warning threshold

    # Alert lead times (days before tarikh_reman_tamat) — UC-2 / E5.
    alert_tiers_days: tuple = (3, 1, 0)

    # Forecast horizon (weeks) and minimum history — UC-3 / E8.
    forecast_horizon_weeks: int = 8
    forecast_min_history_weeks: int = 8

    # LLM narrative: off by default (template narrative is used). Set
    # SMARTDEPOT_LLM=1 to enable the pluggable hook in reporting.narrative.
    enable_llm: bool = field(default_factory=lambda: os.environ.get("SMARTDEPOT_LLM", "0") == "1")

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)


_settings: Settings | None = None


def get_settings(refresh: bool = False) -> Settings:
    """Return the process-wide settings singleton."""
    global _settings
    if _settings is None or refresh:
        _settings = Settings()
        _settings.ensure_dirs()
    return _settings


def today() -> date:
    """Operational 'today' — honours Settings.as_of when set (demos/tests)."""
    return get_settings().as_of or date.today()
