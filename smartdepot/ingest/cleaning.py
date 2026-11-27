"""Cleaning & code-mapping (pipeline stage 2).

Turns raw register rows — with their free-text spelling variants, two-dates-in-
one-cell periods, and stray whitespace — into normalised canonical records.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from ..constants import (
    AGE_BAND_EDGES, AKTA_COMPILED, AKTA_OTHER, AKTA_UNCLEAR, BANGSA_MAP,
    BANGSA_UNKNOWN, DATE_INPUT_FORMATS, DEPOTS, DEPOT_UNKNOWN, GENDER_MAP,
    GENDER_UNKNOWN, NATIONALITY_ETHNIC_MAP, NATIONALITY_MAP, NATIONALITY_UNKNOWN,
    REMAN_PERIOD_RE, REPEAT_KEYWORDS, SECTION_RE, SOURCE_TO_CANONICAL,
    TINDAKAN_PENDING,
)

# Issue severities: "hard" blocks the row, "soft" warns but keeps it.
HARD = "hard"
SOFT = "soft"


def issue(code: str, severity: str, message: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message}


# ---------------------------------------------------------------------------
# Scalar normalisers
# ---------------------------------------------------------------------------
def _txt(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_header(name: str) -> str:
    """Map a raw (possibly space-padded) header to a canonical column name."""
    return SOURCE_TO_CANONICAL.get(name.strip().upper(), name.strip().lower())


def normalize_code_map(df_columns: list[str]) -> dict[str, str]:
    """Return the rename map for a raw column list (implemented in loader)."""
    return {c: normalize_header(c) for c in df_columns}


def _parse_single_date(text: Any) -> date | None:
    """Parse a single date cell (dd.mm.yyyy, dd-mm-yyyy, ISO, ...)."""
    raw = _txt(text)
    if not raw:
        return None
    for fmt in DATE_INPUT_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def parse_period(tarikh_masuk: Any, tarikh_tamat: Any) -> tuple[date | None, date | None, str | None]:
    """Resolve (start, end, error) from a register row.

    Supports the real layout — two single-date columns ``TARIKH MASUK`` +
    ``TARIKH TAMAT REMAN`` — and the legacy combined ``DD.MM.YYYY-DD.MM.YYYY``.
    """
    start = _parse_single_date(tarikh_masuk)
    end = _parse_single_date(tarikh_tamat)
    if start is not None and end is not None:
        return (start, end, "end_before_start") if end < start else (start, end, None)

    # Legacy fallback: the end cell may hold a full range.
    s2, e2, err = parse_reman_period(tarikh_tamat)
    start = start or s2
    end = end or e2
    if err == "end_before_start":
        return start, end, "end_before_start"
    if end is None:
        return start, end, (err or "unparseable_period")
    return start, end, None


def parse_reman_period(text: Any) -> tuple[date | None, date | None, str | None]:
    """Parse 'DD.MM.YYYY-DD.MM.YYYY' into (start, end, error) — legacy layout."""
    raw = _txt(text)
    if not raw:
        return None, None, "blank_period"
    matches = REMAN_PERIOD_RE.findall(raw)
    if len(matches) < 2:
        # Fall back to ISO range "YYYY-MM-DD YYYY-MM-DD".
        iso = re.findall(r"(\d{4})-(\d{2})-(\d{2})", raw)
        if len(iso) >= 2:
            start = _mkdate(iso[0][2], iso[0][1], iso[0][0])
            end = _mkdate(iso[1][2], iso[1][1], iso[1][0])
            if start and end:
                return start, end, None
        return None, None, "unparseable_period"
    start = _mkdate(matches[0][0], matches[0][1], matches[0][2])
    end = _mkdate(matches[1][0], matches[1][1], matches[1][2])
    if start is None or end is None:
        return start, end, "unparseable_period"
    if end < start:
        return start, end, "end_before_start"
    return start, end, None


def _mkdate(day: Any, month: Any, year: Any) -> date | None:
    try:
        d, m, y = int(day), int(month), int(year)
        if y < 100:
            y += 2000
        return date(y, m, d)
    except (ValueError, TypeError):
        return None


def normalize_nationality(value: Any) -> str:
    raw = _txt(value).lower().replace(".", "")
    if not raw or raw in {"-", "nil", "tiada", "tidak dinyatakan", "unknown"}:
        return NATIONALITY_UNKNOWN
    # combined values like "filipina / indonesia" -> take the first.
    raw = re.split(r"[/,;+]", raw)[0].strip()
    if raw in NATIONALITY_MAP:
        return NATIONALITY_MAP[raw]
    if raw in NATIONALITY_ETHNIC_MAP:
        return NATIONALITY_ETHNIC_MAP[raw]
    for key, canon in NATIONALITY_MAP.items():
        if key and key in raw:
            return canon
    return "Lain-lain"


def normalize_bangsa(value: Any) -> str:
    raw = _txt(value).lower().strip()
    if not raw or raw in {"-", "nil", "tiada", "tidak dinyatakan"}:
        return BANGSA_UNKNOWN
    raw = re.split(r"[/,;+]", raw)[0].strip()
    if raw in BANGSA_MAP:
        return BANGSA_MAP[raw]
    for key, canon in BANGSA_MAP.items():
        if key and key in raw:
            return canon
    return "Lain-lain"


def normalize_gender(value: Any) -> tuple[str, bool]:
    """Return (gender, is_valid). Numbers/symbols are flagged invalid."""
    raw = _txt(value).lower()
    if raw in GENDER_MAP:
        return GENDER_MAP[raw], True
    if not raw:
        return GENDER_UNKNOWN, False
    return GENDER_UNKNOWN, False


def classify_akta(kesalahan: Any) -> str:
    raw = _txt(kesalahan)
    if not raw or raw in {"-", "nil", "tiada"}:
        return AKTA_UNCLEAR
    for group, pattern in AKTA_COMPILED:
        if pattern.search(raw):
            return group
    return AKTA_OTHER


def extract_seksyen(kesalahan: Any) -> str:
    """Pull a clean section code, e.g. '6(1)( C ) Immg' -> '6(1)(C)'."""
    raw = _txt(kesalahan).upper()
    match = SECTION_RE.search(raw)
    if not match:
        return ""
    section = f"{match.group(1)}({match.group(2)})"
    if match.group(3):
        section += f"({match.group(3).upper()})"
    return section


def classify_tindakan(value: Any) -> str:
    raw = _txt(value).upper()
    if not raw:
        return TINDAKAN_PENDING
    if "BATAL" in raw:
        return "BATAL PAS"
    if "BEBAS" in raw:
        return "BEBAS DENGAN AMARAN"
    if any(k in raw for k in ("USIR", "USR", "RAI", "BLI", "DEPORT")):
        if "BLI" in raw:
            return "USIR + BLI"
        if "RAI" in raw:
            return "USIR + RAI"
        return "USIR"
    if any(k in raw for k in ("DNA", "RAYUAN", "TANGGAH", "PENDING", "BELUM")):
        return TINDAKAN_PENDING
    return TINDAKAN_PENDING


def age_band(umur: Any) -> str:
    try:
        age = int(umur)
    except (TypeError, ValueError):
        return "-"
    for lo, hi, label in AGE_BAND_EDGES:
        if lo <= age <= hi:
            return label
    return "-"


def is_repeat(catatan: Any) -> bool:
    raw = _txt(catatan).upper()
    return any(k in raw for k in REPEAT_KEYWORDS)


def normalize_depot(value: Any) -> str:
    raw = _txt(value).upper()
    return raw if raw in DEPOTS else DEPOT_UNKNOWN


def clean_no_reman(value: Any) -> str:
    return re.sub(r"\s+", "", _txt(value)).upper()


def clean_fail(value: Any) -> str:
    return _txt(value)


# ---------------------------------------------------------------------------
# Row-level cleaning
# ---------------------------------------------------------------------------
def clean_row(raw: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Normalise one raw row into a canonical record + list of issues."""
    issues: list[dict[str, str]] = []

    no_reman = clean_no_reman(raw.get("no_reman"))
    if not no_reman:
        issues.append(issue("blank_no_reman", HARD, "NO.REMAN is blank"))

    tarikh_masuk = _txt(raw.get("tarikh_masuk"))
    start, end, period_err = parse_period(tarikh_masuk, raw.get("tarikh_tamat_reman_raw"))
    if period_err == "end_before_start":
        issues.append(issue("end_before_start", HARD,
                            "Reman end date is before the start date"))
    elif period_err:
        issues.append(issue(period_err, HARD, "Reman period could not be parsed"))
    if end is not None and start is None:
        issues.append(issue("blank_tarikh_masuk", SOFT,
                            "TARIKH MASUK is blank; reman length unknown"))

    gender, gender_ok = normalize_gender(raw.get("jantina"))
    if not gender_ok:
        issues.append(issue("bad_jantina", SOFT,
                            "JANTINA is not LELAKI/PEREMPUAN (age typed in wrong column?)"))

    try:
        umur = int(float(raw.get("umur_thn")))
    except (TypeError, ValueError):
        umur = None
        issues.append(issue("bad_umur", SOFT, "UMUR is missing or non-numeric"))

    fail = clean_fail(raw.get("fail"))
    if not fail:
        issues.append(issue("blank_fail", SOFT, "FAIL (file number) is blank"))

    depot = normalize_depot(raw.get("depot"))
    if depot == DEPOT_UNKNOWN:
        issues.append(issue("bad_depot", SOFT, "DEPOT is blank or NIL"))

    record: dict[str, Any] = {
        "no_reman": no_reman,
        "tarikh_masuk": tarikh_masuk,
        "nama": _txt(raw.get("nama")).upper(),
        "jantina": gender,
        "umur_thn": umur,
        "bangsa": normalize_bangsa(raw.get("bangsa")),
        "warganegara": normalize_nationality(raw.get("warganegara")),
        "dokumen": _txt(raw.get("dokumen")) or "NIL",
        "nama_pegawai": _txt(raw.get("nama_pegawai")),
        "fail": fail,
        "depot": depot,
        "catatan": _txt(raw.get("catatan")),
        "tindakan": _txt(raw.get("tindakan")).upper(),
        "kesalahan": _txt(raw.get("kesalahan")),
        "tarikh_tamat_reman_raw": _txt(raw.get("tarikh_tamat_reman_raw")),
        "tarikh_reman_mula": start,
        "tarikh_reman_tamat": end,
    }
    return record, issues


def clean_dataframe(df) -> tuple[list[dict], list[tuple[dict, list[dict]]]]:
    """Clean a raw DataFrame.

    Returns (clean_rows, rejects) where rejects are (raw_row, issues) that
    contain a hard error.
    """
    rename = {c: normalize_header(c) for c in df.columns}
    df = df.rename(columns=rename)
    clean_rows: list[dict] = []
    rejects: list[tuple[dict, list[dict]]] = []
    for _, row in df.iterrows():
        raw = row.to_dict()
        record, issues = clean_row(raw)
        if any(i["severity"] == HARD for i in issues):
            rejects.append((raw, issues))
        else:
            record["_issues"] = issues
            clean_rows.append(record)
    return clean_rows, rejects
