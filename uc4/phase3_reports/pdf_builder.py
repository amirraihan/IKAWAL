"""Monthly Executive PDF builder (UC-4) using ReportLab."""

from __future__ import annotations

import datetime as dt
import io
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


class _UC4Canvas(pdf_canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            self._draw_footer(total)
            super().showPage()
        super().save()

    def _draw_footer(self, total: int):
        w = self._pagesize[0]
        self.setFont("Helvetica", 7.5)
        self.setFillColorRGB(0.45, 0.52, 0.62)
        self.drawString(
            36, 18,
            "SmartDepot IKAWAL · UC-4 Laporan Bulanan & AI Insight (Bebas Data Peribadi)",
        )
        self.drawRightString(w - 36, 18, f"Halaman {self._pageNumber} / {total}")


def _kpi_box(value: str, label: str, sub: str = "") -> Table:
    v_p = Paragraph(
        f'<font size="14" color="#0A1E3F"><b>{escape(value)}</b></font>',
        ParagraphStyle("kv", fontName="Helvetica-Bold", alignment=1, leading=16),
    )
    l_p = Paragraph(
        f'<font size="6.5" color="#4A5D7A"><b>{escape(label.upper())}</b></font>',
        ParagraphStyle("kl", fontName="Helvetica-Bold", alignment=1, leading=8),
    )
    rows = [[v_p], [l_p]]
    if sub:
        rows.append([Paragraph(
            f'<font size="6.5" color="#0E7C7B">{escape(sub)}</font>',
            ParagraphStyle("ks", fontName="Helvetica", alignment=1, leading=8),
        )])
    tbl = Table(rows)
    tbl.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return tbl


def _std_table(data: list[list[Any]], col_widths: list[float], header_hex: str = "#12305F") -> Table:
    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_hex)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#CED8E6")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFD")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return tbl


def build_monthly_pdf(
    kpi_payload: dict[str, Any],
    narrative_result: dict[str, Any],
    review_meta: dict[str, Any] | None = None,
) -> bytes:
    """Build a portrait A4 executive monthly report PDF from UC-4 Phase 1 & Phase 2 outputs."""
    buf = io.BytesIO()
    page = A4
    doc = SimpleDocTemplate(
        buf,
        pagesize=page,
        leftMargin=36,
        rightMargin=36,
        topMargin=78,
        bottomMargin=32,
        title=f"Laporan Bulanan UC-4 - {kpi_payload['month_label']}",
    )
    W = page[0]
    avail = W - 72
    styles = getSampleStyleSheet()
    h_style = ParagraphStyle(
        "uc4_h", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10.5,
        textColor=colors.HexColor("#0A1E3F"), spaceBefore=8, spaceAfter=5,
    )
    body_style = ParagraphStyle(
        "uc4_body", parent=styles["Normal"], fontName="Helvetica", fontSize=8.8,
        leading=13, textColor=colors.HexColor("#1E2D45"), spaceAfter=6,
    )
    meta_style = ParagraphStyle(
        "uc4_meta", parent=styles["Normal"], fontName="Helvetica", fontSize=8,
        leading=11, textColor=colors.HexColor("#4A5D7A"),
    )

    review = review_meta or {}
    status_code = review.get("status", "draft")
    if status_code == "released":
        status_text = f"DISAHKAN OLEH: {review.get('reviewed_by') or 'Penganalisis'} ({review.get('reviewed_at') or '-'})"
    else:
        status_text = "STATUS: DRAF (MENUNGGU SEMAKAN PENGANALISIS)"

    def draw_header(canv, _doc):
        canv.saveState()
        canv.setFillColorRGB(10 / 255, 30 / 255, 63 / 255)
        canv.rect(0, page[1] - 60, W, 60, stroke=0, fill=1)
        canv.setFillColorRGB(20 / 255, 200 / 255, 182 / 255)
        canv.rect(0, page[1] - 63, W, 3, stroke=0, fill=1)
        canv.setFillColorRGB(1, 1, 1)
        canv.setFont("Helvetica-Bold", 13.5)
        canv.drawString(36, page[1] - 26, "IRINGKAWAL ANALYZER — LAPORAN BULANAN EKSEKUTIF (UC-4)")
        canv.setFont("Helvetica", 8.5)
        canv.setFillColorRGB(203 / 255, 219 / 255, 240 / 255)
        canv.drawString(
            36, page[1] - 42,
            f"Bahagian Pengurusan Kesalahan (BPK) · Tempoh: {kpi_payload['month_label']}",
        )
        canv.drawRightString(
            W - 36, page[1] - 42,
            "Dijana: " + dt.datetime.now().strftime("%d/%m/%Y %H:%M"),
        )
        canv.setFont("Helvetica-Bold", 7.2)
        canv.setFillColorRGB(130 / 255, 235 / 255, 222 / 255)
        canv.drawString(36, page[1] - 54, status_text)
        canv.restoreState()

    story: list[Any] = []
    k = kpi_payload["kpis"]
    mom = kpi_payload["mom"]
    pct = mom.get("total_pct_change")
    mom_sub = (
        f"{'+' if mom['total_delta'] >= 0 else ''}{mom['total_delta']} ({pct}%)"
        if pct is not None else "Tiada rekod lalu"
    )

    # 1. KPI Summary Strip
    kpi_items = [
        _kpi_box(str(k["total_reman"]), "Jumlah Reman", mom_sub),
        _kpi_box(str(k["aktif"]), "Aktif", f"Bebas: {k['bebas']}"),
        _kpi_box(str(k["urgent_atau_tertunggak"]), "Mendesak <=3h", "Perlu tindakan"),
        _kpi_box(str(k["tempoh_lebih_14_hari"]), "Lebih 14 Hari", "Lanjutan"),
        _kpi_box(str(k["pegawai"]["jumlah_pegawai_aktif"]), "Pegawai Aktif", f"Purata: {k['pegawai']['purata_kes_per_pegawai']}"),
    ]
    kpi_tbl = Table([kpi_items], colWidths=[avail / 5] * 5)
    kpi_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F3F7FC")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#C5D3E6")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#C5D3E6")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(kpi_tbl)
    story.append(Spacer(1, 10))

    # 2. AI Executive Narrative
    guard = narrative_result.get("numeric_guard") or {}
    guard_txt = "LULUS (0 angka tidak berpadanan)" if guard.get("passed") else f"AMARAN ({guard.get('untraced_numbers')})"
    story.append(Paragraph("1. RUMUSAN EKSEKUTIF & NARATIF AI", h_style))
    story.append(Paragraph(
        f"Mod Penjanaan: {escape(str(narrative_result.get('mode', '-')))} · "
        f"Semakan Ketepatan Angka: {escape(guard_txt)} · Privasi: PII Tahanan Dikecualikan",
        meta_style,
    ))
    story.append(Spacer(1, 4))
    narrative_text = narrative_result.get("narrative_text") or ""
    for para in [p.strip() for p in narrative_text.split("\n\n") if p.strip()]:
        story.append(Paragraph(escape(para), body_style))

    # 3. Rule Insights (E9)
    story.append(Paragraph("2. INSIGHT AUTOMATIK (ENJIN PERATURAN E9)", h_style))
    ins_rows = [["Tahap", "Kod", "Tajuk & Huraian"]]
    for ins in kpi_payload.get("insights") or []:
        ins_rows.append([
            str(ins.get("severity", "")).upper(),
            str(ins.get("code", "")),
            Paragraph(
                f"<b>{escape(str(ins.get('title', '')))}</b><br/>{escape(str(ins.get('detail', '')))}",
                ParagraphStyle("ins_p", fontName="Helvetica", fontSize=7.8, leading=10),
            ),
        ])
    story.append(_std_table(ins_rows, [68, 92, avail - 160], header_hex="#0D7A5F"))
    story.append(Spacer(1, 8))

    # 4. Depot & Act MoM Comparison
    story.append(Paragraph(f"3. PERBANDINGAN BULANAN ({escape(mom['prev_month_label'])} -> {escape(kpi_payload['month_label'])})", h_style))
    dep_rows = [["Depot", "Bulan Semasa", "Bulan Lalu", "Perubahan", "% Perubahan"]]
    for d in mom.get("depots") or []:
        dpct = f"{d['pct_change']}%" if d.get("pct_change") is not None else "-"
        dep_rows.append([d["name"], str(d["current"]), str(d["previous"]), f"{d['delta']:+d}", dpct])
    story.append(_std_table(dep_rows, [avail * 0.36, avail * 0.16, avail * 0.16, avail * 0.16, avail * 0.16]))
    story.append(Spacer(1, 8))

    act_rows = [["Kategori Akta", "Bulan Semasa", "Bulan Lalu", "Perubahan", "% Perubahan"]]
    for a in mom.get("akta") or []:
        apct = f"{a['pct_change']}%" if a.get("pct_change") is not None else "-"
        act_rows.append([a["name"], str(a["current"]), str(a["previous"]), f"{a['delta']:+d}", apct])
    story.append(_std_table(act_rows, [avail * 0.36, avail * 0.16, avail * 0.16, avail * 0.16, avail * 0.16]))
    story.append(Spacer(1, 8))

    # 5. Nationality & Top Sections
    story.append(Paragraph("4. PECAHAN WARGANEGARA & SEKSYEN UTAMA", h_style))
    nat_rows = [["Warganegara", "Jumlah", "Peratus"]]
    for w in k.get("warganegara", [])[:8]:
        nat_rows.append([w["name"], str(w["count"]), f"{w['pct']}%"])
    story.append(_std_table(nat_rows, [avail * 0.6, avail * 0.2, avail * 0.2]))
    story.append(Spacer(1, 6))

    sec_rows = [["Seksyen Kesalahan (Dinormalisasi)", "Jumlah", "Peratus"]]
    for s in k.get("top_seksyen", [])[:8]:
        sec_rows.append([s["name"], str(s["count"]), f"{s['pct']}%"])
    story.append(_std_table(sec_rows, [avail * 0.6, avail * 0.2, avail * 0.2]))
    story.append(Spacer(1, 8))

    # 6. Officer Workload & UC-2 / UC-3 / Data Quality
    story.append(Paragraph("5. BEBAN KERJA PEGAWAI & INTEGRASI UC-2 / UC-3", h_style))
    off_rows = [["Pegawai Penyiasat", "Jumlah Kes", "Peratus"]]
    for o in k["pegawai"].get("senarai", [])[:10]:
        off_rows.append([o["name"], str(o["count"]), f"{o['pct']}%"])
    story.append(_std_table(off_rows, [avail * 0.6, avail * 0.2, avail * 0.2]))
    story.append(Spacer(1, 6))

    uc2 = kpi_payload.get("uc2_summary") or {}
    uc3 = kpi_payload.get("uc3_forecast") or {}
    dq = k.get("kualiti_data") or {}
    uc3_fc = ", ".join(f"{dep}: {val}/bln" for dep, val in (uc3.get("anggaran_kemasukan_bulanan_depot") or {}).items()) or "-"
    meta_rows = [
        ["Komponen", "Status / Sumber", "Ringkasan"],
        ["UC-2 Decision Support", str(uc2.get("source", "-")), f"Mendesak/Tertunggak: {uc2.get('kes_mendesak_atau_tertunggak', 0)} · Rayuan: {uc2.get('kes_rayuan_aktif', 0)}"],
        ["UC-3 Forecast", str(uc3.get("source", "-")), f"Unjuran asas depot: {uc3_fc}"],
        ["Kualiti Data", "Semakan Automatik", f"No. Reman kosong: {dq.get('nombor_reman_kosong', 0)} · Tamat < Masuk: {dq.get('tarikh_tamat_sebelum_masuk', 0)} · Tahun janggal: {dq.get('tahun_tamat_janggal', 0)}"],
    ]
    story.append(_std_table(meta_rows, [avail * 0.25, avail * 0.27, avail * 0.48], header_hex="#0A1E3F"))

    doc.build(story, onFirstPage=draw_header, onLaterPages=draw_header, canvasmaker=_UC4Canvas)
    return buf.getvalue()
