"""Privacy / masking utilities (E10).

``NAMA`` and ``CATATAN`` are personal data. They are masked on the dashboard and
in exports for roles that are not cleared, and are never sent to the LLM.
"""

from __future__ import annotations

import re
from typing import Any

# Malaysian IC (e.g. 900101-14-5566), generic 12-digit IDs, and phone numbers.
_IC_RE = re.compile(r"\b\d{6}[- ]?\d{2}[- ]?\d{4}\b")
_LONG_DIGITS_RE = re.compile(r"\b\d{10,}\b")
_PHONE_RE = re.compile(r"\b01\d[- ]?\d{3,4}[- ]?\d{4}\b")

_REDACTED = "[REDACTED]"


def contains_pii(text: str | None) -> bool:
    """True when free text looks like it holds an ID or phone number."""
    if not text:
        return False
    return bool(_IC_RE.search(text) or _LONG_DIGITS_RE.search(text) or _PHONE_RE.search(text))


def mask_name(name: str | None) -> str:
    """Keep the first letter of each token, star out the rest: 'ALI BIN ABU' -> 'A** B** A**'."""
    if not name:
        return ""
    tokens = [t for t in re.split(r"\s+", str(name).strip()) if t]
    return " ".join(t[0] + "*" * max(len(t) - 1, 0) for t in tokens)


def mask_catatan(text: str | None) -> str:
    """Redact embedded IDs / phone numbers while keeping readable flags."""
    if not text:
        return ""
    out = str(text)
    out = _IC_RE.sub(_REDACTED, out)
    out = _PHONE_RE.sub(_REDACTED, out)
    out = _LONG_DIGITS_RE.sub(_REDACTED, out)
    return out


def sanitize_for_llm(text: str | None) -> str:
    """Hard guarantee for the report narrative: never emit personal data."""
    return mask_catatan(text)


def mask_record(record: dict[str, Any], reveal_pii: bool) -> dict[str, Any]:
    """Return a copy of a reman record with PII masked when not cleared."""
    out = dict(record)
    if not reveal_pii:
        out["nama"] = mask_name(out.get("nama"))
        out["catatan"] = mask_catatan(out.get("catatan"))
    return out
