"""Minimal PDF table writer using only the standard library.

Produces a landscape A4 report with the base-14 Helvetica fonts, so the
hash-locked runtime image needs no reportlab. Text is ASCII/Latin-1; characters
outside that set are transliterated. Long cells wrap to multiple lines and the
content paginates automatically.
"""
from __future__ import annotations

_PAGE = (842.0, 595.0)  # A4 landscape in points
_MARGIN = 28.0
_TITLE_SIZE = 14.0
_SUB_SIZE = 8.5
_FONT_SIZE = 7.6
_LEADING = _FONT_SIZE + 2.6
_CHAR_FACTOR = 0.52

_TRANSLIT = {
    '\u2264': '<=', '\u2265': '>=', '\u2013': '-', '\u2014': '-', '\u2019': "'",
    '\u2018': "'", '\u201c': '"', '\u201d': '"', '\u2022': '-', '\u00b7': '-', '\u00a0': ' ',
}


def _clean(text) -> str:
    value = '' if text is None else str(text)
    out = []
    for raw in value:
        mapped = _TRANSLIT.get(raw, raw)
        out.append(''.join(char if ord(char) <= 255 else '?' for char in mapped))
    return ''.join(out)


def _escape(text: str) -> str:
    return text.replace('\\', r'\\').replace('(', r'\(').replace(')', r'\)')


def _wrap(text: str, width: float) -> list[str]:
    max_chars = max(1, int(width / (_FONT_SIZE * _CHAR_FACTOR)))
    lines: list[str] = []
    current = ''
    for word in _clean(text).split():
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= max_chars:
            current += ' ' + word
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or ['']


def _assemble(objects: list[bytes], root_ref: int) -> bytes:
    out = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f'{number} 0 obj\n'.encode('latin-1') + body + b'\nendobj\n'
    xref = len(out)
    size = len(objects) + 1
    out += f'xref\n0 {size}\n'.encode('latin-1')
    out += b'0000000000 65535 f \n'
    for offset in offsets[1:]:
        out += f'{offset:010d} 00000 n \n'.encode('latin-1')
    out += f'trailer\n<< /Size {size} /Root {root_ref} 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode('latin-1')
    return bytes(out)


def table_pdf(title: str, subtitle: str, headers: list[str], rows: list[list], weights: list[float] | None = None) -> bytes:
    """Render a table to PDF bytes. ``weights`` set relative column widths."""
    page_w, page_h = _PAGE
    avail = page_w - 2 * _MARGIN
    weights = list(weights or [1.0] * len(headers))
    total = sum(weights) or 1.0
    widths = [avail * weight / total for weight in weights]
    x_offsets, running = [], _MARGIN
    for width in widths:
        x_offsets.append(running + 2)
        running += width

    header_cells = [_wrap(header, width) for header, width in zip(headers, widths)]
    header_height = max(len(cell) for cell in header_cells) * _LEADING + 6
    title_height = _TITLE_SIZE + _SUB_SIZE + 16
    usable = (page_h - _MARGIN - title_height) - _MARGIN

    pages: list[list[list[list[str]]]] = []
    body: list[list[list[str]]] = []
    used = 0.0
    for row in rows:
        cells = [_wrap(value, width) for value, width in zip(row, widths)]
        height = max(len(cell) for cell in cells) * _LEADING + 4
        if body and used + height > usable:
            pages.append(body)
            body, used = [], 0.0
        body.append(cells)
        used += height
    if body or not pages:
        pages.append(body)

    contents: list[bytes] = []
    for index, rows_on_page in enumerate(pages, start=1):
        ops: list[str] = []
        y = page_h - _MARGIN
        ops.append(f'BT /F2 {_TITLE_SIZE} Tf {_MARGIN:.2f} {y:.2f} Td ({_escape(_clean(title))}) Tj ET')
        y -= _TITLE_SIZE + 3
        subtitle_full = f'{_clean(subtitle)}  (halaman {index}/{len(pages)})'
        ops.append(f'BT /F1 {_SUB_SIZE} Tf {_MARGIN:.2f} {y:.2f} Td ({_escape(subtitle_full)}) Tj ET')
        y -= _SUB_SIZE + 10
        ops.append(f'0.9 w 0.16 0.16 0.16 RG {_MARGIN:.2f} {y - header_height:.2f} m {page_w - _MARGIN:.2f} {y - header_height:.2f} l S')
        for column, cell in enumerate(header_cells):
            for line_number, line in enumerate(cell):
                baseline = y - 9 - line_number * _LEADING
                ops.append(f'BT /F2 {_FONT_SIZE} Tf {x_offsets[column]:.2f} {baseline:.2f} Td ({_escape(line)}) Tj ET')
        y -= header_height
        for cells in rows_on_page:
            height = max(len(cell) for cell in cells) * _LEADING + 4
            for column, cell in enumerate(cells):
                for line_number, line in enumerate(cell):
                    baseline = y - 9 - line_number * _LEADING
                    ops.append(f'BT /F1 {_FONT_SIZE} Tf {x_offsets[column]:.2f} {baseline:.2f} Td ({_escape(line)}) Tj ET')
            ops.append(f'0.4 w 0.75 0.75 0.75 RG {_MARGIN:.2f} {y - height:.2f} m {page_w - _MARGIN:.2f} {y - height:.2f} l S')
            y -= height
        contents.append(('\n'.join(ops)).encode('latin-1'))

    objects: list[bytes] = [b'', b'']
    objects.append(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>')  # 3
    objects.append(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>')  # 4
    kids: list[str] = []
    for content in contents:
        page_number = len(objects) + 1
        content_number = len(objects) + 2
        objects.append(
            f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_w:.0f} {page_h:.0f}] '
            f'/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {content_number} 0 R >>'.encode('latin-1')
        )
        objects.append(b'<< /Length ' + str(len(content)).encode('latin-1') + b' >>\nstream\n' + content + b'\nendstream')
        kids.append(f'{page_number} 0 R')
    objects[0] = b'<< /Type /Catalog /Pages 2 0 R >>'
    objects[1] = f'<< /Type /Pages /Kids [{" ".join(kids)}] /Count {len(kids)} >>'.encode('latin-1')
    return _assemble(objects, 1)
