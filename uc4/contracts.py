"""Shared data contracts & privacy guardrails across UC-4 phases.

Import flow is strictly one-way:
    contracts -> phase1_kpi -> phase2_narrative -> phase3_reports -> app/phase4_ui
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "1.0"

# Fields that contain personal / case-identifying information and must NEVER
# appear inside aggregated KPI snapshots sent to Phase 2 (LLM / narrative).
FORBIDDEN_PII_KEYS = frozenset({
    "nama",
    "catatan",
    "nombor_reman",
    "nombor_fail",
    "ic",
    "passport",
})


def contains_forbidden_keys(obj: Any, path: str = "") -> list[str]:
    """Return dotted paths for any forbidden PII key present in a nested structure."""
    hits: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            key_lower = str(k).strip().lower()
            here = f"{path}.{k}" if path else str(k)
            if key_lower in FORBIDDEN_PII_KEYS:
                hits.append(here)
            hits.extend(contains_forbidden_keys(v, here))
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            hits.extend(contains_forbidden_keys(item, f"{path}[{idx}]"))
    return hits


def assert_kpi_payload_safe(payload: dict[str, Any]) -> None:
    """Raise ValueError if a KPI snapshot leaks forbidden PII keys."""
    hits = contains_forbidden_keys(payload)
    if hits:
        raise ValueError(f"Privacy guard blocked PII keys in KPI payload: {hits}")


def to_json(payload: dict[str, Any], pretty: bool = False) -> str:
    """Serialize a UC-4 contract payload to UTF-8 JSON."""
    if pretty:
        return json.dumps(payload, ensure_ascii=False, indent=2)
    return json.dumps(payload, ensure_ascii=False)
