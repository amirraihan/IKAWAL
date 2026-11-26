"""Standalone CLI entrypoint for UC-4 Phase 2.

Usage:
    python -m uc4.phase2_narrative --month 2026-10 --pretty
    python -m uc4.phase2_narrative --in uc4_kpi_2026-10.json --pretty
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from uc4.contracts import to_json
from uc4.phase1_kpi.engine import build_monthly_kpi, load_records_from_sqlite
from uc4.phase2_narrative.generator import generate_narrative


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m uc4.phase2_narrative",
        description="Jana naratif eksekutif daripada KPI Phase 1 dengan pengawal angka (UC-4 Phase 2).",
    )
    parser.add_argument("--in", dest="in_file", default=None, help="Fail JSON output Phase 1")
    parser.add_argument("--db", default=None, help="Laluan SQLite jika tidak guna --in")
    parser.add_argument("--month", default=None, help="Bulan YYYY-MM jika jana terus dari DB")
    parser.add_argument("--mode", default="auto", choices=["auto", "fallback", "llm"])
    parser.add_argument("--out", default=None, help="Simpan output JSON naratif ke fail ini")
    parser.add_argument("--pretty", action="store_true", help="Format JSON dengan indentasi")
    args = parser.parse_args(argv)

    if args.in_file:
        with open(args.in_file, "r", encoding="utf-8") as fh:
            kpi_payload = json.load(fh)
    else:
        records = load_records_from_sqlite(args.db)
        kpi_payload = build_monthly_kpi(records, month_ym=args.month)

    narrative = generate_narrative(kpi_payload, mode=args.mode)
    rendered = to_json(narrative, pretty=args.pretty)

    if args.out:
        out_dir = os.path.dirname(os.path.abspath(args.out))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(rendered + "\n")
        print(f"Naratif disimpan ke {args.out} (mode={narrative['mode']}, guard={narrative['numeric_guard']['passed']})")
    else:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
