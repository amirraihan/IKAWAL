"""Locate the reman register and turn its rows into scored UC-2 cases.

Read-only and dependency-free at runtime (see ``app/xlsx.py``). The workbook is
found through an explicit path (``APP_REMAN_FILE``) or a short search path so the
same code works locally and when an operator mounts the file.
"""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from . import xlsx
from .reman import Case, build_case

# Register headers after trimming the leading space found on ' FAIL'.
FIELDS = (
    'TARIKH MASUK', 'TARIKH TAMAT REMAN', 'NAMA', 'JANTINA', 'UMUR (THN)', 'BANGSA', 'WARGANEGARA',
    'NO.REMAN', 'DOKUMEN', 'NAMA PEGAWAI', 'FAIL', 'DEPOT', 'CATATAN', 'TINDAKAN', 'KESALAHAN',
)
_SHEET = 'Sheet1'


class RegisterMissing(FileNotFoundError):
    """Raised when no readable register workbook can be found."""


def _candidate_folders(root: Path) -> tuple[Path, ...]:
    """Project-local data folders first, then the shared repo-level ``data/``."""
    return (root / 'data', root / 'app' / 'data', root / '.local', root.parent / 'data')


def resolve_reman_file(root: Path, configured: str = '') -> Path | None:
    """Return the register path, or None. Order: configured, data folders, common names."""
    if configured:
        candidate = Path(configured)
        if not candidate.is_absolute():
            candidate = root / candidate
        return candidate if candidate.is_file() else None
    for directory in _candidate_folders(root):
        if directory.is_dir():
            found = sorted(directory.glob('*.xlsx'))
            if found:
                return found[0]
    for name in ('reman.xlsx', 'iringkawal_bpk2026.xlsx', 'iringkawal_BPK_2026 - dummy FILLED.xlsx', 'iringkawal BPK 2026 - dummy (FILLED).xlsx'):
        for base in (root, root.parent):
            candidate = base / name
            if candidate.is_file():
                return candidate
    return None


def read_table(path: Path) -> list[list[str]]:
    if path.suffix.lower() == '.csv':
        with path.open(newline='', encoding='utf-8-sig') as handle:
            return [row for row in csv.reader(handle)]
    return xlsx.read_rows(path, sheet=_SHEET)


def _map_rows(rows: list[list[str]]) -> list[dict]:
    header_index, columns = None, {}
    for index, row in enumerate(rows[:10]):
        cells = [str(cell).strip() for cell in row]
        if 'NO.REMAN' in cells and 'TARIKH TAMAT REMAN' in cells:
            header_index = index
            columns = {name: cells.index(name) for name in cells if name in FIELDS}
            break
    if header_index is None:
        return []
    records = []
    for row in rows[header_index + 1:]:
        if not any(str(cell).strip() for cell in row):
            continue
        records.append({field: (row[position] if position < len(row) else '') for field, position in columns.items()})
    return records


def _cache_token(path: Path) -> tuple:
    stat = path.stat()
    return (str(path), stat.st_mtime_ns, stat.st_size)


_CACHE: dict[tuple, tuple] = {}


def load_cases(path: Path, today: date, capacity_pressure_for: set[str] | None = None) -> list[Case]:
    """Read, map and score the register. Cached on the file token and today's date."""
    token = (_cache_token(path), today, tuple(sorted(capacity_pressure_for or ())))
    cached = _CACHE.get(token)
    if cached is not None:
        return [case for case in cached]
    pressure = capacity_pressure_for or set()
    cases = [
        build_case(record, today, index=position, capacity_pressure=(record.get('DEPOT', '').strip().upper() in pressure))
        for position, record in enumerate(_map_rows(read_table(path)), start=2)
    ]
    _CACHE.clear()
    _CACHE[token] = tuple(cases)
    return cases


def load_from_settings(root: Path, configured: str, today: date, capacity_pressure_for: set[str] | None = None) -> tuple[Path, list[Case]]:
    path = resolve_reman_file(root, configured)
    if path is None:
        raise RegisterMissing(
            'Tiada daftar reman dijumpai. Tetapkan APP_REMAN_FILE, atau letakkan fail .xlsx dalam data/, app/data/, .local/ atau folder data/ repositori.'
        )
    return path, load_cases(path, today, capacity_pressure_for)
