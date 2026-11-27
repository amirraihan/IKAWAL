"""Access control & audit helpers (E10).

Roles: officer, depot_head, hq. Permissions here are intentionally simple so a
real identity provider (SSO) can be dropped in later.
"""

from __future__ import annotations

from .constants import ROLE_CAN_SEE_PII, ROLES


def is_valid_role(role: str) -> bool:
    return role in ROLES


def can_reveal_pii(role: str) -> bool:
    """Officers see masked names; depot heads and HQ are cleared for names."""
    return role in ROLE_CAN_SEE_PII


def can_export(role: str) -> bool:
    """Downloads are available to every authenticated role."""
    return role in ROLES


def scope_depots(role: str, depot: str | None, depot_head_of: str | None = None) -> str | None:
    """Return the depot a role is constrained to (None = all depots).

    A depot head is limited to their own depot; HQ sees everything.
    """
    if role == "depot_head" and depot_head_of:
        return depot_head_of
    return depot
