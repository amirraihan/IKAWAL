"""Draft paperwork (E5): pre-filled extension / outcome documents (DOCX).

Advisory and pre-filled only — the officer reviews, approves and submits. The
system never files automatically (design UC-2 status note).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..masking import mask_name, sanitize_for_llm

try:
    from docx import Document  # python-docx
    _HAS_DOCX = True
except Exception:  # pragma: no cover
    _HAS_DOCX = False


def _slug(text: Any) -> str:
    return "".join(c if c.isalnum() else "-" for c in str(text)).strip("-") or "kes"


def _rows(context: dict[str, Any]) -> list[tuple[str, str]]:
    return [
        ("No. Reman", context.get("no_reman", "")),
        ("Nama (bertopeng)", mask_name(context.get("nama"))),
        ("Warganegara", context.get("warganegara", "")),
        ("Depot", context.get("depot", "")),
        ("Pegawai Penyiasat", context.get("nama_pegawai", "")),
        ("Kesalahan", f"{context.get('seksyen', '')} — {context.get('akta', '')}".strip(" —")),
        ("Tempoh Reman",
         f"{context.get('tarikh_reman_mula', '')} hingga {context.get('tarikh_reman_tamat', '')}"),
        ("Tempoh (hari)", str(context.get("tempoh_reman", ""))),
        ("Baki Hari", str(context.get("hari_berbaki", ""))),
        ("Tindakan Semasa", context.get("tindakan_kod", "")),
        ("Catatan", sanitize_for_llm(context.get("catatan", ""))),
    ]


def _write(title: str, context: dict[str, Any], decision_line: str, path: Path) -> Path:
    rows = _rows(context)
    if _HAS_DOCX:
        doc = Document()
        doc.add_heading(title, level=1)
        table = doc.add_table(rows=0, cols=2)
        table.style = "Table Grid"
        for label, value in rows:
            cells = table.add_row().cells
            cells[0].text = str(label)
            cells[1].text = str(value)
        doc.add_paragraph("")
        doc.add_paragraph(decision_line)
        doc.add_paragraph(f"Disediakan pada: {context.get('disediakan_pada', '')}")
        doc.add_paragraph("Tandatangan pegawai: ____________________")
        doc.save(str(path))
        return path
    text_path = path.with_suffix(".txt")
    lines = [title, ""] + [f"{k}: {v}" for k, v in rows] + ["", decision_line]
    text_path.write_text("\n".join(lines), encoding="utf-8")
    return text_path


def render_extension_draft(context: dict[str, Any], output_dir: Path) -> Path:
    """Pre-filled application to extend a remand period."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"lanjutan-reman-{_slug(context.get('no_reman'))}.docx"
    return _write("DRAF PERMOHONAN LANJUTAN REMAN", context,
                  "Dimohon lanjutan tempoh reman bagi membolehkan siasatan diselesaikan.", path)


def render_outcome_draft(context: dict[str, Any], output_dir: Path) -> Path:
    """Pre-filled outcome (usir / bebas) record."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"tindakan-{_slug(context.get('no_reman'))}.docx"
    return _write("DRAF REKOD TINDAKAN / PENGELUARAN", context,
                  "Tindakan dicadangkan berdasarkan status reman dan hasil siasatan. "
                  "Sila sahkan sebelum dikemukakan.", path)
