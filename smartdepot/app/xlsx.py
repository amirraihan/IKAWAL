"""Minimal read-only .xlsx reader using only the standard library.

The runtime image installs dependencies with ``--require-hashes`` from
``requirements.lock.txt``, so UC-2 reads the register without adding pandas or
openpyxl. This module understands the parts of the format the register uses:
shared strings, inline strings, numbers and booleans in the first worksheet.
It does not evaluate formulas or write files.
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

_CELL = re.compile(r'^([A-Z]+)(\d+)$')


def _local(tag: str) -> str:
    return tag.rsplit('}', 1)[-1]


def _column_index(reference: str) -> int:
    """Return a zero-based column index from an A1-style reference."""
    match = _CELL.match(reference.upper())
    if not match:
        return 0
    index = 0
    for char in match.group(1):
        index = index * 26 + (ord(char) - ord('A') + 1)
    return index - 1


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        data = archive.read('xl/sharedStrings.xml')
    except KeyError:
        return []
    strings: list[str] = []
    for item in ElementTree.fromstring(data):
        if _local(item.tag) != 'si':
            continue
        strings.append(''.join(node.text or '' for node in item.iter() if _local(node.tag) == 't'))
    return strings


def _first_sheet_path(archive: zipfile.ZipFile) -> str:
    names = set(archive.namelist())
    if 'xl/workbook.xml' not in names or 'xl/_rels/workbook.xml.rels' not in names:
        return 'xl/worksheets/sheet1.xml'
    relationships = {}
    for rel in ElementTree.fromstring(archive.read('xl/_rels/workbook.xml.rels')):
        relationships[rel.get('Id')] = rel.get('Target', '')
    for sheet in ElementTree.fromstring(archive.read('xl/workbook.xml')).iter():
        if _local(sheet.tag) != 'sheet':
            continue
        target = ''
        for key, value in sheet.attrib.items():
            if _local(key) == 'id':
                target = relationships.get(value, '')
                break
        if target:
            return target.lstrip('/') if target.startswith('xl/') else ('xl/' + target.lstrip('/'))
    return 'xl/worksheets/sheet1.xml'


def _cell_text(cell, shared: list[str]) -> str:
    kind = cell.get('t')
    value = None
    inline = None
    for child in cell:
        name = _local(child.tag)
        if name == 'v':
            value = child.text
        elif name == 'is':
            inline = ''.join(node.text or '' for node in child.iter() if _local(node.tag) == 't')
    if kind == 's' and value is not None:
        index = int(value)
        return shared[index] if 0 <= index < len(shared) else ''
    if kind == 'inlineStr':
        return inline or ''
    if kind == 'b':
        return 'TRUE' if value == '1' else 'FALSE'
    return value if value is not None else ''


def read_rows(path: str | Path, sheet: str | None = None, limit: int | None = None) -> list[list[str]]:
    """Return the worksheet as a rectangular list of string rows.

    ``sheet`` selects a worksheet by name (defaults to the first sheet). Empty
    rows are returned as empty lists so row counts stay meaningful.
    """
    with zipfile.ZipFile(path) as archive:
        shared = _shared_strings(archive)
        target = _first_sheet_path(archive)
        rows: list[list[str]] = []
        for row in ElementTree.fromstring(archive.read(target)).iter():
            if _local(row.tag) != 'row':
                continue
            values: dict[int, str] = {}
            for cell in row:
                if _local(cell.tag) != 'c':
                    continue
                reference = cell.get('r') or ''
                values[_column_index(reference) if reference else len(values)] = _cell_text(cell, shared)
            width = (max(values) + 1) if values else 0
            rows.append([values.get(i, '') for i in range(width)])
            if limit is not None and len(rows) >= limit:
                break
    return rows
