"""Standalone CLI / 1st-of-month scheduled runner for UC-4 Phase 3.

Usage:
    python -m uc4.phase3_reports --month 2026-10 --out-dir reports_out
    python -m uc4.phase3_reports --schedule-monthly --out-dir reports_out
"""

from __future__ import annotations

import argparse
import datetime as dt
import os

from uc4.phase1_kpi.engine import build_monthly_kpi, load_records_from_sqlite, prev_month_ym
from uc4.phase2_narrative.generator import generate_narrative
from uc4.phase3_reports.pdf_builder import build_monthly_pdf
from uc4.phase3_reports.xlsx_builder import build_monthly_xlsx


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m uc4.phase3_reports",
        description="Jana Laporan Bulanan PDF & Lampiran XLSX (UC-4 Phase 3).",
    )
    parser.add_argument("--db", default=None, help="Laluan SQLite (default: ikawal.db)")
    parser.add_argument("--month", default=None, help="Bulan YYYY-MM")
    parser.add_argument("--schedule-monthly", action="store_true", help="Guna bulan kalendar sebelumnya (sesuai tugas 1hb)")
    parser.add_argument("--mode", default="auto", choices=["auto", "fallback", "llm"])
    parser.add_argument("--out-dir", default="uc4_output", help="Direktori output PDF & XLSX")
    args = parser.parse_args(argv)

    target_month = args.month
    if args.schedule_monthly and not target_month:
        curr_ym = dt.date.today().strftime("%Y-%m")
        target_month = prev_month_ym(curr_ym)

    records = load_records_from_sqlite(args.db)
    kpi = build_monthly_kpi(records, month_ym=target_month)
    narrative = generate_narrative(kpi, mode=args.mode)

    pdf_bytes = build_monthly_pdf(kpi, narrative)
    xlsx_bytes = build_monthly_xlsx(kpi, narrative)

    os.makedirs(args.out_dir, exist_ok=True)
    pdf_path = os.path.join(args.out_dir, f"IKAWAL_UC4_Laporan_{kpi['month']}.pdf")
    xlsx_path = os.path.join(args.out_dir, f"IKAWAL_UC4_Lampiran_{kpi['month']}.xlsx")

    with open(pdf_path, "wb") as fh:
        fh.write(pdf_bytes)
    with open(xlsx_path, "wb") as fh:
        fh.write(xlsx_bytes)

    print(f"PDF dijana : {pdf_path} ({len(pdf_bytes)} bytes)")
    print(f"XLSX dijana: {xlsx_path} ({len(xlsx_bytes)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
