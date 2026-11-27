"""E7 — Decision support: one recommended action per case; overrides logged."""

from __future__ import annotations

from typing import Any

from ..constants import ACTION_BY_LABEL, TINDAKAN_FINAL, TINDAKAN_PENDING

DECISION_ACCEPT = "Accept"
DECISION_OVERRIDE = "Override"


def recommend_action(record: dict[str, Any]) -> str:
    """One recommended next action, derived from the risk label.

    Advisory only — the officer accepts or overrides.
    """
    label = record.get("risk_label")
    if label in ACTION_BY_LABEL:
        action = ACTION_BY_LABEL[label]
    else:
        action = "Monitor."
    # Small, explainable refinements on top of the label mapping.
    if record.get("tindakan_kod") in TINDAKAN_FINAL:
        return "Kes selesai — sahkan dokumen dan tutup fail."
    if record.get("alert_tier") == "overdue" and record.get("tindakan_kod") == TINDAKAN_PENDING:
        return ("Segera: tetapkan TINDAKAN atau mohon lanjutan reman; maklum Ketua Depot.")
    return action


def apply_recommendation(record: dict[str, Any]) -> dict[str, Any]:
    record["recommended_action"] = recommend_action(record)
    return record


def log_decision(repo, no_reman: str, recommended: str, decision: str,
                 override_action: str | None = None, reason: str | None = None,
                 actor: str = "officer") -> None:
    """Record an officer's accept/override decision (E7 + E10 audit trail)."""
    repo.save_decision(no_reman, recommended, decision, override_action, reason, actor)
    repo.log_event(
        "decision", no_reman=no_reman, actor=actor,
        details={"decision": decision, "override_action": override_action,
                 "reason": reason, "recommended": recommended},
    )
