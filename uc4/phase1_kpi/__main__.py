"""Standalone CLI entrypoint for UC-4 Phase 1.

Usage:
    python -m uc4.phase1_kpi --month 2026-10 --pretty
"""

from __future__ import annotations

import argparse
import os
import sys

from uc4.contracts import to_json
from uc4.phase1_kpi.engine import build_monthly_kpi, load_records_from_sqlite


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m uc4.phase1_kpi",
        description="Jana ringkasan KPI bulanan & insight berasaskan peraturan (UC-4 Phase 1).",
    )
    parser.add_argument("--db", default=None, help="Laluan ke fail SQLite (default: ikawal.db)")
    parser.add_argument("--month", default=None, help="Bulan sasaran YYYY-MM (default: bulan terkini dalam DB)")
    parser.add_argument("--out", default=None, help="Simpan output JSON ke fail ini")
    parser.add_argument("--pretty", action="store_true", help="Format JSON dengan indentasi")
    args = parser.parse_args(argv)

    records = load_records_from_sqlite(args.db)
    payload = build_monthly_kpi(records, month_ym=args.month)
    rendered = to_json(payload, pretty=args.pretty)

    if args.out:
        out_dir = os.path.dirname(os.path.abspath(args.out))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(rendered + "\n")
        print(f"Disimpan ke {args.out} ({payload['kpis']['total_reman']} rekod untuk {payload['month']})")
    else:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
