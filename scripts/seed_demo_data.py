"""Generate a synthetic reman register that mirrors the KPIs in the design doc,
then ingest it through the real cleaning/validation pipeline.

Usage:  python scripts/seed_demo_data.py [--rows 2115] [--db PATH] [--reset]

The data is entirely fictional (no real people). It deliberately includes the
same data-quality defects the design document reports (blank NO.REMAN,
end-before-start periods, spelling variants, an IC number inside CATATAN) so the
cleaning layer has something to fix.
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from smartdepot.config import get_settings  # noqa: E402
from smartdepot.db import init_db  # noqa: E402
from smartdepot.ingest.loader import ingest_excel  # noqa: E402
from smartdepot.repository import RepanRepository  # noqa: E402

FIRST = ["AHMAD", "MOHD", "ABU", "ALI", "HASSAN", "ISMAIL", "OSMAN", "JUAN", "PEDRO",
         "MARIA", "ROSA", "LINA", "SITI", "NUR", "FATIMAH", "JOSEPH", "CARLOS", "RAMON",
         "BUDI", "AGUS", "SANTI", "DEWI", "RIZAL", "ANDI"]
MIDDLE = ["BIN", "BINTI", "A/L", "A/P", "BT", "DELA", "DE"]
LAST = ["ABDULLAH", "RAHMAN", "SANTOS", "CRUZ", "REYES", "SUSILO", "WIJAYA", "KUMAR",
        "RAJAN", "TAN", "LIM", "IBRAHIM", "YUSOF", "HASSAN", "SALLEH"]

OFFICERS = ["KP RAMLI", "SJN AZIZ", "SGT LEE", "INSP TAN", "ASP NG", "SI ADNAN",
            "KS MUTHU", "PW SITI", "KPL ZAIN", "INSP GOH"]

NATIONALITY_VARIANTS = {
    "Filipina": ["FILIPINA", " FILIPINA", "PHL", "FILIPINAS", "FILIPINA ", "BAJAU", "SULUK"],
    "Indonesia": ["INDONESIA", "INDON", "IDN", "INDONESIA "],
    "India": ["INDIA", "INDIAN"],
    "Thailand": ["THAI", "THAILAND"],
    "Myanmar": ["MYANMAR", "BURMA"],
    "Bangladesh": ["BANGLADESH", "BANGLA"],
    "Vietnam": ["VIETNAM"],
    "China": ["CHINA", "CHINA P.R."],
}
NAT_WEIGHTS = [("Filipina", 0.815), ("Indonesia", 0.157), ("India", 0.01),
               ("Thailand", 0.006), ("Myanmar", 0.004), ("Bangladesh", 0.003),
               ("Vietnam", 0.003), ("China", 0.002)]

BANGSA_VARIANTS = {
    "Bajau": ["BAJAU", "Badjau"], "Suluk": ["SULUK", "Sulu", "Tausug"],
    "Bugis": ["BUGIS"], "Bisaya": ["BISAYA", "VISAYA"], "Jawa": ["JAWA"],
    "Sunda": ["SUNDA"], "Melayu": ["MELAYU", "Malay"],
}

KESALAHAN_IMIGRESEN = ["6(1)(C) IMMG", "6(1)( C ) Immg", "6(1)(c) Akta Imigresen",
                       "15(1)(c) IMMG", "6(3) IMMG", "56(1)(d) IMMG"]
KESALAHAN_DADAH = ["39B ADB 1952", "12(2) ADB 1952", "ADB 1952 Seksyen 39B",
                   "39A(1) ADB", "6 ADB 1952"]
KESALAHAN_KANUN = ["379 KK", "420 Kanun Keseksaan", "323 KK", "392 KK"]
KESALAHAN_OTHER = [".", "-", "", "Akta Kastam 1967 S135", "ATIPSOM 2007 S12"]

TINDAKAN_VARIANTS = ["USIR", "USIR / RAI", "USIR/RAI", "USR", "USIR + BLI",
                     "BEBAS DENGAN AMARAN", "BEBAS", "UJIAN DNA", "RAYUAN", ""]

CATATAN_FLAGS = ["", "", "", "", "", "", "TANGKAP SEMULA", "TAHAN SEMULA",
                 "rayuan dalam proses", "kes tangkap semula"]


def _name(rng: random.Random) -> str:
    parts = [rng.choice(FIRST)]
    if rng.random() < 0.6:
        parts.append(rng.choice(MIDDLE))
    parts.append(rng.choice(LAST))
    return " ".join(parts)


def _nationality(rng: random.Random) -> str:
    r = rng.random()
    acc = 0.0
    chosen = "Filipina"
    for nat, w in NAT_WEIGHTS:
        acc += w
        if r <= acc:
            chosen = nat
            break
    return rng.choice(NATIONALITY_VARIANTS[chosen])


def _bangsa(rng: random.Random, nat_raw: str) -> str:
    up = nat_raw.strip().upper()
    if up in {"BAJAU", "SULUK"}:
        return rng.choice(BANGSA_VARIANTS["Bajau" if up == "BAJAU" else "Suluk"])
    if up.startswith("FILIPINA") or up == "PHL":
        return rng.choice(BANGSA_VARIANTS["Bisaya"])
    if up.startswith("INDONESIA") or up == "IDN":
        return rng.choice(BANGSA_VARIANTS["Bugis"] + BANGSA_VARIANTS["Jawa"])
    return rng.choice(list(BANGSA_VARIANTS["Melayu"]) + ["-"])


def _kesalahan(rng: random.Random, group: str) -> str:
    table = {
        "imigresen": KESALAHAN_IMIGRESEN,
        "dadah": KESALAHAN_DADAH,
        "kanun": KESALAHAN_KANUN,
        "other": KESALAHAN_OTHER,
    }
    val = rng.choice(table[group])
    if rng.random() < 0.03:  # two offences in one cell
        val = f"{val} / {rng.choice(KESALAHAN_DADAH)}"
    return val


def build_register(rows: int, as_of: date, seed: int = 42) -> pd.DataFrame:
    rng = random.Random(seed)
    records = []
    di_share = 1144 / 2115  # DIKK vs DIP split from the doc
    for i in range(1, rows + 1):
        depot = "DIKK" if rng.random() < di_share else "DIP"
        nat = _nationality(rng)
        bangsa = _bangsa(rng, nat)
        age = rng.randint(18, 65)
        gender = "LELAKI" if rng.random() < 0.82 else "PEREMPUAN"

        # reman period: 92% are 14 days; some extensions
        span = rng.choices([14, 15, 45, 7], weights=[92, 3, 3, 2])[0]
        # weight start dates toward recent months so some cases are active today
        if rng.random() < 0.35:
            start = as_of - timedelta(days=rng.randint(0, 60))
        else:
            start = date(2026, 1, 1) + timedelta(days=rng.randint(0, 330))
        end = start + timedelta(days=span - 1)

        # offence mix per the doc
        g = rng.choices(["imigresen", "dadah", "kanun", "other"],
                        weights=[971, 939, 127, 74])[0]
        kesalahan = _kesalahan(rng, g)

        # tindakan mix: mostly USIR, few BEBAS, few pending
        tindakan = rng.choices(
            ["USIR", "BEBAS", "pending"],
            weights=[2050, 55, 10],
        )[0]
        if tindakan == "USIR":
            t_raw = rng.choice(["USIR", "USIR / RAI", "USIR/RAI", "USR", "USIR + BLI"])
        elif tindakan == "BEBAS":
            t_raw = rng.choice(["BEBAS DENGAN AMARAN", "BEBAS"])
        else:
            t_raw = rng.choice(["UJIAN DNA", "RAYUAN", ""])

        catatan = rng.choice(CATATAN_FLAGS)
        if rng.random() < 0.004:  # a stray IC number -> must be masked
            catatan = "Mempunyai kad pengenalan 900101-14-5566; " + catatan

        no_reman = f"26({i:04d})BD"
        records.append({
            "TARIKH MASUK": f"{start:%d.%m.%Y}",
            "TARIKH TAMAT REMAN": f"{end:%d.%m.%Y}",
            "NAMA": _name(rng),
            "JANTINA": gender,
            "UMUR (THN)": age,
            "BANGSA": bangsa,
            "WARGANEGARA": nat,
            "NO.REMAN": no_reman,
            "DOKUMEN": "NIL",
            "NAMA PEGAWAI": rng.choice(OFFICERS),
            " FAIL": f"({rng.randint(1, 40):02d})2026",  # leading space, as in source
            "DEPOT": depot,
            "CATATAN": catatan,
            "TINDAKAN": t_raw,
            "KESALAHAN": kesalahan,
        })

    df = pd.DataFrame(records)

    # --- inject the documented data-quality defects --------------------------
    idx = list(df.index)
    rng.shuffle(idx)

    blank_reman = idx[:256]           # 256 blank NO.REMAN
    for j in blank_reman:
        df.at[j, "NO.REMAN"] = ""

    dup = idx[256:258]                # 2 duplicates
    for j in dup:
        df.at[j, "NO.REMAN"] = df.at[idx[300], "NO.REMAN"]

    bad_dates = idx[258:299]          # 41 end-before-start
    for j in bad_dates:
        df.at[j, "TARIKH MASUK"], df.at[j, "TARIKH TAMAT REMAN"] = (
            df.at[j, "TARIKH TAMAT REMAN"], df.at[j, "TARIKH MASUK"])

    df.at[idx[299], "TARIKH TAMAT REMAN"] = ""     # 1 blank period

    bad_gender = idx[300:326]         # 26 rows with a number in JANTINA
    for j in bad_gender:
        df.at[j, "JANTINA"] = str(rng.randint(18, 65))

    for j in idx[326:331]:            # 5 blank officers
        df.at[j, "NAMA PEGAWAI"] = ""

    for j in idx[331:336]:            # 5 blank depots (one NIL)
        df.at[j, "DEPOT"] = "" if rng.random() < 0.8 else "NIL"

    rng.shuffle(idx)
    return df


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed SmartDepot demo data")
    parser.add_argument("--rows", type=int, default=2115)
    parser.add_argument("--db", default=None)
    parser.add_argument("--reset", action="store_true", help="Delete the DB first")
    args = parser.parse_args()

    settings = get_settings()
    settings.ensure_dirs()

    if args.reset and settings.db_path.exists():
        settings.db_path.unlink()

    df = build_register(args.rows, as_of=date.today())
    xlsx = settings.data_dir / "iringkawal_BPK_2026 - dummy FILLED.xlsx"
    df.to_excel(xlsx, index=False)
    print(f"Wrote {len(df)} rows -> {xlsx}")

    repo = RepanRepository(args.db or settings.db_path)
    init_db(args.db or settings.db_path)
    summary = ingest_excel(xlsx, repo, actor="seed", role="hq")
    print("Ingest summary:", summary.as_dict())
    print("Rejects:", repo.rejects_count(), "| Cases in DB:", repo.count())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
