"""Monthly Excel Appendix builder (UC-4) using openpyxl."""

from __future__ import annotations

import io
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

HEADER_FILL = PatternFill("solid", fgColor="12305F")
SUB_FILL = PatternFill("solid", fgColor="0D7A5F")
HEADER_FONT = Font(bold=True, color="FFFFFF")


def _style_header(ws, row_idx: int = 1, fill: PatternFill = HEADER_FILL) -> None:
    for cell in ws[row_idx]:
        cell.font = HEADER_FONT
        cell.fill = fill
        cell.alignment = Alignment(horizontal="center", vertical="center")


def _autofit(ws, min_width: int = 14, max_width: int = 56) -> None:
    for col in ws.columns:
        letter = openpyxl.utils.get_column_letter(col[0].column)
        longest = max((len(str(c.value or "")) for c in col), default=min_width)
        ws.column_dimensions[letter].width = max(min_width, min(longest + 4, max_width))


def build_monthly_xlsx(
    kpi_payload: dict[str, Any],
    narrative_result: dict[str, Any],
    review_meta: dict[str, Any] | None = None,
) -> bytes:
    """Create a multi-sheet XLSX appendix for UC-4 monthly reporting."""
    wb = openpyxl.Workbook()
    k = kpi_payload["kpis"]
    mom = kpi_payload["mom"]
    review = review_meta or {}

    # Sheet 1: Ringkasan KPI
    ws1 = wb.active
    ws1.title = "1_Ringkasan_KPI"
    ws1.append(["Metrik", "Nilai", "Catatan"])
    _style_header(ws1)
    ws1.append(["Bulan Laporan", kpi_payload["month_label"], kpi_payload["month"]])
    ws1.append(["Status Pengesahan", review.get("status", "draft").upper(), review.get("reviewed_by") or "Belum disahkan"])
    ws1.append(["Tarikh Disahkan", review.get("reviewed_at") or "-", ""])
    ws1.append(["Jumlah Reman (Kohort Bulan)", k["total_reman"], f"Bulan lalu ({mom['prev_month_label']}): {mom['prev_total_reman']}"])
    ws1.append(["Perubahan MoM", mom["total_delta"], f"{mom['total_pct_change']}%" if mom["total_pct_change"] is not None else "-"])
    ws1.append(["Status Aktif", k["aktif"], ""])
    ws1.append(["Status Sudah Bebas", k["bebas"], ""])
    ws1.append(["Kes Mendesak <=3 Hari / Tertunggak", k["urgent_atau_tertunggak"], ""])
    ws1.append(["Kes Tempoh Reman > 14 Hari", k["tempoh_lebih_14_hari"], ""])
    ws1.append(["Bilangan Pegawai Aktif", k["pegawai"]["jumlah_pegawai_aktif"], f"Purata kes/pegawai: {k['pegawai']['purata_kes_per_pegawai']}"])
    _autofit(ws1)

    # Sheet 2: Naratif & Insights
    ws2 = wb.create_sheet("2_Naratif_&_Insights")
    ws2.append(["Jenis", "Kod / Mod", "Tajuk / Butiran"])
    _style_header(ws2, fill=SUB_FILL)
    guard = narrative_result.get("numeric_guard") or {}
    ws2.append(["Semakan Angka", "LULUS" if guard.get("passed") else "GAGAL", f"Bilangan angka disemak: {guard.get('checked_count', 0)}; Tidak berpadanan: {guard.get('untraced_numbers', [])}"])
    for idx, para in enumerate(narrative_result.get("paragraphs") or [narrative_result.get("narrative_text", "")], start=1):
        ws2.append([f"Naratif Perenggan {idx}", narrative_result.get("mode", "-"), para])
    for ins in kpi_payload.get("insights") or []:
        ws2.append([f"Insight ({ins['severity'].upper()})", ins["code"], f"{ins['title']} — {ins['detail']}"])
    _autofit(ws2, max_width=85)

    # Sheet 3: Depot & MoM
    ws3 = wb.create_sheet("3_Depot_&_MoM")
    ws3.append(["Dimensi", "Kategori", "Bulan Semasa", "Bulan Lalu", "Perubahan", "% Perubahan"])
    _style_header(ws3)
    for d in mom.get("depots") or []:
        ws3.append(["Depot", d["name"], d["current"], d["previous"], d["delta"], d["pct_change"]])
    for a in mom.get("akta") or []:
        ws3.append(["Kategori Akta", a["name"], a["current"], a["previous"], a["delta"], a["pct_change"]])
    _autofit(ws3)

    # Sheet 4: Warganegara & Kesalahan (including Infographic Matrix)
    ws4 = wb.create_sheet("4_Warganegara_&_Kesalahan")
    info = kpi_payload.get("infographics", {}).get("kesalahan_setiap_warganegara", {})
    acts = info.get("akta_groups") or []
    ws4.append(["Warganegara", "Jumlah"] + acts)
    _style_header(ws4)
    for row in info.get("rows") or []:
        ws4.append([row["warganegara"], row["jumlah"]] + [row["mengikut_akta"].get(a, 0) for a in acts])
    ws4.append([])
    ws4.append(["Top Seksyen Kesalahan", "Jumlah", "Peratus (%)"])
    _style_header(ws4, row_idx=ws4.max_row, fill=SUB_FILL)
    for s in k.get("top_seksyen") or []:
        ws4.append([s["name"], s["count"], s["pct"]])
    _autofit(ws4)

    # Sheet 5: Tindakan & Pegawai
    ws5 = wb.create_sheet("5_Tindakan_&_Pegawai")
    ws5.append(["Kategori", "Nama", "Jumlah", "Peratus (%)"])
    _style_header(ws5)
    for t in k.get("tindakan") or []:
        ws5.append(["Tindakan", t["name"], t["count"], t["pct"]])
    for p in k["pegawai"].get("senarai") or []:
        ws5.append(["Pegawai", p["name"], p["count"], p["pct"]])
    _autofit(ws5)

    # Sheet 6: UC-2, UC-3 & Kualiti Data
    ws6 = wb.create_sheet("6_UC2_UC3_&_Kualiti")
    ws6.append(["Bahagian", "Medan", "Nilai"])
    _style_header(ws6)
    for key, val in (kpi_payload.get("uc2_summary") or {}).items():
        ws6.append(["UC-2 Adapter", key, str(val)])
    for key, val in (kpi_payload.get("uc3_forecast") or {}).items():
        ws6.append(["UC-3 Adapter", key, str(val)])
    for key, val in (k.get("kualiti_data") or {}).items():
        ws6.append(["Kualiti Data", key, str(val)])
    _autofit(ws6, max_width=75)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
