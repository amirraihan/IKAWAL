"""SmartDepot command-line interface.

Examples
--------
python scripts/cli.py init
python scripts/cli.py seed --reset
python scripts/cli.py ingest "data/iringkawal_BPK_2026 - dummy FILLED.xlsx"
python scripts/cli.py daily --as-of 2026-11-26
python scripts/cli.py monthly --year 2026 --month 11
python scripts/cli.py stats
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smartdepot.db import init_db  # noqa: E402
from smartdepot.ingest.loader import ingest_excel  # noqa: E402
from smartdepot.pipeline import run_daily, run_monthly  # noqa: E402
from smartdepot.repository import RepanRepository  # noqa: E402


def cmd_init(args) -> int:
    init_db(args.db)
    print(f"Initialised database at {args.db or 'default path'}")
    return 0


def cmd_seed(args) -> int:
    import subprocess
    script = Path(__file__).resolve().parent / "seed_demo_data.py"
    cmd = [sys.executable, str(script), "--rows", str(args.rows)]
    if args.db:
        cmd += ["--db", args.db]
    if args.reset:
        cmd.append("--reset")
    return subprocess.call(cmd)


def cmd_ingest(args) -> int:
    repo = RepanRepository(args.db)
    summary = ingest_excel(args.path, repo, actor="cli", role="hq")
    print("Ingest:", summary.as_dict())
    return 0


def cmd_daily(args) -> int:
    repo = RepanRepository(args.db)
    ref = date.fromisoformat(args.as_of) if args.as_of else None
    result = run_daily(repo, as_of=ref)
    print(f"Daily {result['as_of']}: {result['alerts']} alerts, "
          f"{result['forecast']} depots forecast")
    return 0


def cmd_monthly(args) -> int:
    repo = RepanRepository(args.db)
    art = run_monthly(repo, args.year, args.month)
    print(f"Report {art['period']}: {art['xlsx']}")
    return 0


def cmd_stats(args) -> int:
    repo = RepanRepository(args.db)
    df = repo.to_dataframe()
    print(f"Cases: {len(df)} | rejects: {repo.rejects_count()}")
    if not df.empty:
        print("By depot:", df["depot"].value_counts().to_dict())
        print("By status:", df["status_reman"].value_counts().to_dict())
        print("By risk:", df["risk_label"].value_counts().to_dict())
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="smartdepot", description="SmartDepot CLI")
    p.add_argument("--db", default=None)
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init").set_defaults(func=cmd_init)

    s = sub.add_parser("seed"); s.add_argument("--rows", type=int, default=2115)
    s.add_argument("--reset", action="store_true"); s.set_defaults(func=cmd_seed)

    i = sub.add_parser("ingest"); i.add_argument("path"); i.set_defaults(func=cmd_ingest)

    d = sub.add_parser("daily"); d.add_argument("--as-of", default=None)
    d.set_defaults(func=cmd_daily)

    m = sub.add_parser("monthly")
    m.add_argument("--year", type=int, default=date.today().year)
    m.add_argument("--month", type=int, default=date.today().month)
    m.set_defaults(func=cmd_monthly)

    sub.add_parser("stats").set_defaults(func=cmd_stats)
    return p


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
