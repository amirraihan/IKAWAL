"""Loader (E1): Excel upload / form entry -> clean -> validate -> process."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from ..repository import RepanRepository
from .cleaning import clean_dataframe, issue
from .validation import validate_record


@dataclass
class IngestSummary:
    source: str
    total: int = 0
    loaded: int = 0
    updated: int = 0
    rejected: int = 0
    reject_issues: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "total": self.total,
            "loaded": self.loaded,
            "updated": self.updated,
            "rejected": self.rejected,
        }


def _existing_keys(repo: RepanRepository) -> set[str]:
    return {r["no_reman"] for r in repo.all_reman() if r.get("no_reman")}


def ingest_dataframe(df: pd.DataFrame, repo: RepanRepository,
                     actor: str = "system", role: str = "officer",
                     source: str = "excel") -> IngestSummary:
    """Clean, validate and store every row of a raw DataFrame."""
    from ..pipeline import compute_depot_occupancy, process_record  # local import avoids cycle

    summary = IngestSummary(source=source, total=len(df))
    clean_rows, rejects = clean_dataframe(df)
    existing = _existing_keys(repo)
    seen: set[str] = set()
    occ = compute_depot_occupancy(repo)

    for raw, issues in rejects:
        summary.rejected += 1
        summary.reject_issues.append({"raw": raw, "issues": issues})
        repo.add_reject(source, {k: v for k, v in raw.items()}, [i["code"] for i in issues])

    for record in clean_rows:
        key = record.get("no_reman", "")
        row_issues = list(record.pop("_issues", []))
        row_issues += validate_record(record, existing | seen)
        if key in seen:
            row_issues.append(issue("duplicate_in_file", "hard",
                                    "Duplicate NO.REMAN within the uploaded file"))
        if any(i["severity"] == "hard" for i in row_issues):
            summary.rejected += 1
            summary.reject_issues.append({"raw": record, "issues": row_issues})
            repo.add_reject(source, record, [i["code"] for i in row_issues])
            continue

        seen.add(key)
        was_update = key in existing
        process_record(record, repo, actor=actor, role=role, source=source,
                       extra_issues=row_issues, depot_occupancy=occ)
        if was_update:
            summary.updated += 1
        else:
            summary.loaded += 1
            existing.add(key)

    repo.log_event("ingest", actor=actor, role=role, details=summary.as_dict())
    return summary


def ingest_excel(path: str | Path, repo: RepanRepository,
                 sheet: str | int = 0, actor: str = "system",
                 role: str = "officer") -> IngestSummary:
    """Load an Excel register file (header whitespace trimmed on read)."""
    df = pd.read_excel(path, sheet_name=sheet, dtype=str)
    return ingest_dataframe(df, repo, actor=actor, role=role,
                            source=f"excel:{Path(path).name}")


def ingest_form(form, repo: RepanRepository, actor: str = "officer",
                role: str = "officer") -> dict[str, Any]:
    """Store a single reman captured on the entry form, then run the engines."""
    from ..pipeline import process_record  # local import avoids import cycle

    record = form.to_record()
    issues = validate_record(record, _existing_keys(repo))
    return process_record(record, repo, actor=actor, role=role, source="manual",
                          extra_issues=issues)
