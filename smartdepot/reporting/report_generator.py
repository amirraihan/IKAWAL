"""Monthly report generator (E9 / UC-4).

Produces the monthly report as XLSX + DOCX + HTML (and PDF when reportlab is
available), with narrative generated strictly from the KPI table.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from .kpis import kpi_snapshot, breakdowns, monthly_summary, overview_kpis
from .narrative import build_narrative

try:
    from openpyxl import Workbook
    _HAS_XLSX = True
except Exception:  # pragma: no cover
    _HAS_XLSX = False

try:
    from docx import Document
    _HAS_DOCX = True
except Exception:  # pragma: no cover
    _HAS_DOCX = False

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as _pdf_canvas
    _HAS_PDF = True
except Exception:  # pragma: no cover
    _HAS_PDF = False


def generate_monthly_report(df: pd.DataFrame, year: int, month: int,
                            output_dir: Path) -> dict[str, Any]:
    """Generate all report artefacts for one month; return their paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot = kpi_snapshot(df, year, month)
    narrative = build_narrative(snapshot)
    period = snapshot["period"]

    paths: dict[str, Any] = {"period": period, "narrative": narrative, "snapshot": snapshot}
    paths["xlsx"] = _write_xlsx(snapshot, df, output_dir / f"laporan-{period}.xlsx")
    paths["docx"] = _write_docx(snapshot, narrative, output_dir / f"laporan-{period}.docx")
    paths["html"] = _write_html(snapshot, narrative, output_dir / f"laporan-{period}.html")
    paths["pdf"] = _write_pdf(narrative, output_dir / f"laporan-{period}.pdf")
    return paths


def _breakdown_frames(snapshot: dict[str, Any]) -> dict[str, pd.DataFrame]:
    return snapshot["breakdowns"]


def _write_xlsx(snapshot: dict[str, Any], df: pd.DataFrame, path: Path) -> Path:
    if not _HAS_XLSX:
        path = path.with_suffix(".csv")
        pd.DataFrame([snapshot["overview"]]).to_csv(path, index=False)
        return path
    wb = Workbook()
    ws = wb.active
    ws.title = "Ringkasan"
    ws.append(["KPI", f"Nilai ({snapshot['period']})", "Perubahan vs bulan lepas"])
    for k, v in snapshot["overview"].items():
        ws.append([k, v, snapshot["change"].get(k)])
    for name, frame in _breakdown_frames(snapshot).items():
        sheet = wb.create_sheet(name[:31])
        sheet.append(list(frame.columns))
        for _, row in frame.iterrows():
            sheet.append(list(row.values))
    trend = wb.create_sheet("Trend")
    trend.append(["bulan", "bilangan"])
    for _, row in snapshot["monthly_trend"].iterrows():
        trend.append([row["bulan"], int(row["bilangan"])])
    wb.save(path)
    return path


def _write_docx(snapshot: dict[str, Any], narrative: str, path: Path) -> Path:
    if not _HAS_DOCX:
        path = path.with_suffix(".txt")
        path.write_text(narrative, encoding="utf-8")
        return path
    doc = Document()
    doc.add_heading(f"Laporan Bulanan SmartDepot — {snapshot['period']}", level=1)
    for line in narrative.splitlines():
        doc.add_paragraph(line)
    for name, frame in _breakdown_frames(snapshot).items():
        doc.add_heading(name.capitalize(), level=2)
        table = doc.add_table(rows=1, cols=len(frame.columns))
        table.style = "Light Grid Accent 1"
        for i, col in enumerate(frame.columns):
            table.rows[0].cells[i].text = str(col)
        for _, row in frame.head(15).iterrows():
            cells = table.add_row().cells
            for i, val in enumerate(row.values):
                cells[i].text = str(val)
    doc.save(path)
    return path


def _write_html(snapshot: dict[str, Any], narrative: str, path: Path) -> Path:
    parts = [
        "<!DOCTYPE html><html lang='ms'><head><meta charset='utf-8'>",
        f"<title>Laporan SmartDepot {snapshot['period']}</title>",
        "<style>body{font:15px/1.55 system-ui,Segoe UI,Arial;max-width:900px;margin:2rem auto;padding:0 1rem;color:#12203a}",
        "table{border-collapse:collapse;width:100%;margin:0.6rem 0 1.4rem}th,td{border:1px solid #d9e0ec;padding:6px 8px;text-align:left}",
        "th{background:#eef3fa}pre{white-space:pre-wrap;background:#f7f9fd;padding:1rem;border-radius:8px;border-left:4px solid #2f7dc4}</style>",
        "</head><body>",
        f"<h1>Laporan Bulanan SmartDepot — {snapshot['period']}</h1>",
        "<pre>" + narrative + "</pre>",
    ]
    for name, frame in _breakdown_frames(snapshot).items():
        parts.append(f"<h2>{name.capitalize()}</h2>")
        parts.append(frame.to_html(index=False, border=0))
    parts.append("<p><em>Angka dijana daripada jadual reman yang dibersihkan. Tiada data peribadi.</em></p>")
    parts.append("</body></html>")
    path.write_text("\n".join(parts), encoding="utf-8")
    return path


def _write_pdf(narrative: str, path: Path) -> Path | None:
    if not _HAS_PDF:
        return None
    pdf = _pdf_canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    y = height - 60
    pdf.setFont("Helvetica", 10)
    for line in narrative.splitlines():
        if y < 60:
            pdf.showPage()
            pdf.setFont("Helvetica", 10)
            y = height - 60
        pdf.drawString(50, y, line[:110])
        y -= 16
    pdf.save()
    return path


def export_case_list(df: pd.DataFrame, path: Path, reveal_pii: bool = False) -> Path:
    """Export a (masked by default) case list to XLSX/CSV for download (E10)."""
    from ..masking import mask_record

    rows = [mask_record(r, reveal_pii) for r in df.to_dict("records")]
    out = pd.DataFrame(rows)
    if _HAS_XLSX:
        out.to_excel(path, index=False)
        return path
    path = path.with_suffix(".csv")
    out.to_csv(path, index=False)
    return path
