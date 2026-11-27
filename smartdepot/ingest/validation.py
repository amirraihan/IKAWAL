"""Validation rules (pipeline stages 2 & 5).

Hard rules block a row; soft rules warn and the record is kept and flagged.
"""

from __future__ import annotations

from typing import Any, Iterable

from .cleaning import HARD, SOFT, issue

REQUIRED_FIELDS = ("no_reman", "nama", "tarikh_reman_tamat")


def validate_record(record: dict[str, Any],
                    existing_keys: Iterable[str] = ()) -> list[dict[str, str]]:
    """Return the full issue list for a cleaned record (adds duplicate check)."""
    issues: list[dict[str, str]] = []

    for field in REQUIRED_FIELDS:
        value = record.get(field)
        if value in (None, "", 0) and field != "umur_thn":
            issues.append(issue(f"missing_{field}", HARD, f"{field} is required"))

    if record.get("no_reman") and record["no_reman"] in set(existing_keys):
        issues.append(issue("duplicate_no_reman", HARD,
                            "NO.REMAN already exists in the register"))

    start, end = record.get("tarikh_reman_mula"), record.get("tarikh_reman_tamat")
    if start and end and end < start:
        issues.append(issue("end_before_start", HARD,
                            "Reman end date is before the start date"))

    umur = record.get("umur_thn")
    if umur is not None and (umur < 15 or umur > 100):
        issues.append(issue("umur_out_of_range", SOFT, f"UMUR={umur} is unusual"))
    return issues


def split_issues(issues: list[dict[str, str]]) -> tuple[list, list]:
    """Return (hard, soft) issue lists."""
    hard = [i for i in issues if i["severity"] == HARD]
    soft = [i for i in issues if i["severity"] == SOFT]
    return hard, soft


def is_valid(issues: list[dict[str, str]]) -> bool:
    """A record is valid when it has no hard issues."""
    return not any(i["severity"] == HARD for i in issues)
