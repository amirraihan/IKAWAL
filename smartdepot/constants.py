"""Domain constants: source columns, code lists, and rule weights.

Everything that the design document calls a "code list" or an "illustrative
weight" lives here so the depot head / legal unit can tune values in one place.

Aligned with the real dataset ``data/iringkawal_bpk2026.xlsx`` (15 columns).
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Source columns (real register). Note the leading space on " FAIL"; the loader
# trims header whitespace.
# ---------------------------------------------------------------------------
SOURCE_TO_CANONICAL: dict[str, str] = {
    "TARIKH MASUK": "tarikh_masuk",
    "TARIKH TAMAT REMAN": "tarikh_tamat_reman_raw",
    "NAMA": "nama",
    "JANTINA": "jantina",
    "UMUR (THN)": "umur_thn",
    "BANGSA": "bangsa",
    "WARGANEGARA": "warganegara",
    "NO.REMAN": "no_reman",
    "DOKUMEN": "dokumen",
    "NAMA PEGAWAI": "nama_pegawai",
    "FAIL": "fail",
    "DEPOT": "depot",
    "CATATAN": "catatan",
    "TINDAKAN": "tindakan",
    "KESALAHAN": "kesalahan",
}

CANONICAL_SOURCE_COLUMNS: list[str] = [
    "tarikh_masuk", "tarikh_tamat_reman_raw", "nama", "jantina", "umur_thn",
    "bangsa", "warganegara", "no_reman", "dokumen", "nama_pegawai", "fail",
    "depot", "catatan", "tindakan", "kesalahan",
]

# Derived fields (section 2.2) — the feature layer, E3.
DERIVED_COLUMNS: list[str] = [
    "tarikh_reman_mula", "tarikh_reman_tamat", "tempoh_reman", "hari_berbaki",
    "status_reman", "akta", "seksyen", "tindakan_kod", "kumpulan_umur",
    "flag_ulang",
]

# Engine outputs stored alongside each case.
ENGINE_COLUMNS: list[str] = [
    "risk_score", "risk_label", "risk_reasons", "alert_tier", "recommended_action",
]

REMAN_PERIOD_RE = re.compile(r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})")
# Section code, with an optional letter on the number and an optional (letter)
# suffix, e.g. "39A(1)", "6(1)(C)", "120 (1)", "15(1)(a)".
SECTION_RE = re.compile(
    r"(\d+[A-Za-z]?)\s*\(\s*(\d+)\s*\)\s*(?:\(\s*([A-Za-z])\s*\))?"
)

DATE_INPUT_FORMATS = ("%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%y")

# ---------------------------------------------------------------------------
# Dropdown code lists (E1). The entry form uses these; the importer maps
# free-text spellings onto them.
# ---------------------------------------------------------------------------
NATIONALITY_MAP: dict[str, str] = {
    "filipina": "Filipina", "filipinas": "Filipina", "philippines": "Filipina",
    "phl": "Filipina", "ph": "Filipina", "pilipina": "Filipina",
    "indonesia": "Indonesia", "indon": "Indonesia", "idn": "Indonesia", "ri": "Indonesia",
    "india": "India", "indian": "India", "ind": "India",
    "thailand": "Thailand", "thai": "Thailand", "tha": "Thailand", "siam": "Thailand",
    "myanmar": "Myanmar", "burma": "Myanmar", "mmr": "Myanmar",
    "vietnam": "Vietnam", "viet nam": "Vietnam", "vnm": "Vietnam",
    "bangladesh": "Bangladesh", "bangla": "Bangladesh", "bgd": "Bangladesh",
    "pakistan": "Pakistan", "pak": "Pakistan", "pakistani": "Pakistan",
    "china": "China", "china p.r.": "China", "china pr": "China", "chn": "China",
    "nepal": "Nepal", "npl": "Nepal",
    "sri lanka": "Sri Lanka", "lka": "Sri Lanka",
    "kemboja": "Kemboja", "cambodia": "Kemboja",
    "laos": "Laos", "nigeria": "Nigeria", "somalia": "Somalia",
    "stateless": "Tanpa Kerakyatan", "tiada kerakyatan": "Tanpa Kerakyatan",
    "timor": "Timor-Leste", "timor leste": "Timor-Leste", "timor-leste": "Timor-Leste",
    "buton": "Indonesia",
}
# Ethnic labels seen in WARGANEGARA resolve to the dominant nationality.
NATIONALITY_ETHNIC_MAP: dict[str, str] = {
    "bajau": "Filipina", "suluk": "Filipina", "bugis": "Indonesia",
    "bisaya": "Filipina", "visaya": "Filipina",
}
NATIONALITY_UNKNOWN = "Tidak Dinyatakan"
KNOWN_NATIONALITIES = sorted(set(NATIONALITY_MAP.values()) | {"Lain-lain"})

BANGSA_MAP: dict[str, str] = {
    "bajau": "Bajau", "badjau": "Bajau",
    "suluk": "Suluk", "sulu": "Suluk", "tausug": "Suluk",
    "bugis": "Bugis",
    "bisaya": "Bisaya", "visaya": "Bisaya",
    "jawa": "Jawa", "javanese": "Jawa",
    "sunda": "Sunda", "melayu": "Melayu", "malay": "Melayu",
    "banjar": "Banjar", "minang": "Minang", "minangkabau": "Minang",
    "tagalog": "Tagalog", "kagayan": "Kagayan", "tausug ": "Suluk",
    "timor": "Timor", "buton": "Buton", "tator": "Tator",
    "iban": "Iban", "kadazan": "Kadazan", "dusun": "Dusun", "bajau laut": "Bajau",
}
BANGSA_UNKNOWN = "-"
KNOWN_BANGSA = sorted(set(BANGSA_MAP.values()) | {BANGSA_UNKNOWN, "Lain-lain"})

GENDER_MAP: dict[str, str] = {
    "lelaki": "LELAKI", "l": "LELAKI", "male": "LELAKI", "m": "LELAKI",
    "perempuan": "PEREMPUAN", "p": "PEREMPUAN", "female": "PEREMPUAN", "f": "PEREMPUAN",
}
GENDER_UNKNOWN = "TIDAK DINYATAKAN"

# KESALAHAN -> Act group (section 2.2). Ordered regex rules; first match wins.
AKTA_RULES: list[tuple[str, str]] = [
    ("Akta Imigresen 1959/63", r"\bimmg\b|imigresen|immigration|imigration"),
    ("Akta Dadah Berbahaya 1952", r"\badb\b|dadah|berbahaya|dangerous\s*drugs"),
    ("Kanun Keseksaan", r"\bkk\b|kanun|keseksaan|penal"),
    ("Akta Kastam", r"\bkastam\b|customs"),
    ("Akta Anti-Pemerdagangan Orang 2007", r"atipsom|pemerdagangan|trafficking"),
]
AKTA_COMPILED = [(group, re.compile(pattern, re.IGNORECASE)) for group, pattern in AKTA_RULES]
AKTA_GROUPS: dict[str, tuple] = {g: () for g, _ in AKTA_RULES}  # kept for compatibility
AKTA_OTHER = "Lain-lain"
AKTA_UNCLEAR = "Tidak Jelas"
KNOWN_AKTA = sorted(set(AKTA_GROUPS) | {AKTA_OTHER, AKTA_UNCLEAR})

# TINDAKAN -> outcome code (section 2.2).
TINDAKAN_CODES = [
    "USIR", "USIR + BLI", "USIR + RAI", "BATAL PAS",
    "BEBAS DENGAN AMARAN", "BELUM MUKTAMAD",
]
TINDAKAN_FINAL = {"USIR", "USIR + BLI", "USIR + RAI", "BATAL PAS", "BEBAS DENGAN AMARAN"}
TINDAKAN_PENDING = "BELUM MUKTAMAD"

# Age bands (section 2.2).
AGE_BAND_EDGES = [(18, 29, "18-29"), (30, 44, "30-44"), (45, 59, "45-59"), (60, 200, "60+")]
AGE_BANDS = [label for *_x, label in AGE_BAND_EDGES]

# Repeat-offender keywords in CATATAN (section 2.2 / 5.2).
REPEAT_KEYWORDS = ("TANGKAP SEMULA", "TAHAN SEMULA", "ULANG", "BERULANG")

# Depot codes kept as in the register/design doc; a display map matches the app.
DEPOTS = ["DIKK", "DIP"]
DEPOT_UNKNOWN = "TIDAK DINYATAKAN"
DEPOT_DISPLAY = {"DIKK": "Kota Kinabalu", "DIP": "Papar"}

OFFICER_RANKS = ["KP", "SJN", "SGT", "INSP", "ASP", "SI", "KS", "PW", "KPL"]

# ---------------------------------------------------------------------------
# Risk scoring (E6) — table 5.2 illustrative weights.
# ---------------------------------------------------------------------------
RISK_WEIGHTS: dict[str, int] = {
    "ends_today_or_overdue": 40,
    "ends_in_1_3_days": 25,
    "tindakan_pending": 15,
    "extended_over_14": 10,
    "repeat_case": 10,
    "age_60_plus": 10,
    "admin_gap": 10,
    "depot_near_capacity": 5,
}
RISK_SCORE_CAP = 100

# Label cut-offs (score -> label), table 5.3.
RISK_LABEL_CUTOFFS = [
    (60, "Kritikal"),
    (35, "Tinggi"),
    (15, "Sederhana"),
    (0, "Rendah"),
]

# Recommended next action per label (E7 / table 5.3).
ACTION_BY_LABEL: dict[str, str] = {
    "Kritikal": "Act today: record TINDAKAN (usir / bebas) or apply for extension; escalate to depot head.",
    "Tinggi": "Within 48 h: prepare extension draft or close the DNA / rayuan step.",
    "Sederhana": "This week: fix admin gaps; confirm the deportation arrangement.",
    "Rendah": "Monitor.",
}

# ---------------------------------------------------------------------------
# Access roles (E10).
# ---------------------------------------------------------------------------
ROLES = ("officer", "depot_head", "hq")
ROLE_CAN_SEE_PII = {"depot_head", "hq"}   # officer sees masked names

STD_REMAN_DAYS = 14  # standard remand period; longer implies an extension
