"""Monthly job (1st of month) — UC-4 report generator.

Usage:  python scripts/run_monthly.py [--db PATH] [--year Y --month M]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smartdepot.pipeline import run_monthly  # noqa: E402
from smartdepot.repository import RepanRepository  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="SmartDepot monthly report")
    ap.add_argument("--db", default=None)
    ap.add_argument("--year", type=int, default=date.today().year)
    ap.add_argument("--month", type=int, default=date.today().month)
    args = ap.parse_args()

    repo = RepanRepository(args.db)
    art = run_monthly(repo, args.year, args.month)
    print(f"Monthly report for {art['period']}")
    for key in ("xlsx", "docx", "html", "pdf"):
        if art.get(key):
            print(f"  {key:5s}: {art[key]}")
    print()
    print(art["narrative"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
