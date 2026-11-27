"""Daily job (07:00) — UC-2 alerts + UC-3 forecast.

Usage:  python scripts/run_daily.py [--db PATH] [--as-of YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smartdepot.pipeline import run_daily  # noqa: E402
from smartdepot.repository import RepanRepository  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="SmartDepot daily job")
    ap.add_argument("--db", default=None)
    ap.add_argument("--as-of", default=None, help="reference date YYYY-MM-DD")
    args = ap.parse_args()

    ref = date.fromisoformat(args.as_of) if args.as_of else None
    repo = RepanRepository(args.db)
    result = run_daily(repo, as_of=ref)

    print(f"Daily run for {result['as_of']}")
    print(f"  alerts raised     : {result['alerts']}")
    print(f"  depots forecast   : {result['forecast']}")
    print(f"  capacity warnings : {len(result.get('capacity_warnings', []))}")
    for row in result.get("capacity_warnings", []):
        print(f"    ! {row['depot']} {row['headcount']}/{row['capacity']} "
              f"({row['occupancy_pct']*100:.0f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
