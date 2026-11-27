"""
Iringkawal Analyzer + Supervisor Dashboard - BPK 2026
=====================================================
Full-functional Flask + SQLite web application that mirrors the single-file
`app.html` dashboard. Runnable directly in Visual Studio Code.

Run (VS Code terminal):
    python -m pip install -r requirements.txt
    python app.py
Then open http://127.0.0.1:5000

Demo logins (change via environment variables in production):
    Staff Iringkawal : staff2026
    Penyelia         : penyelia2026
    Boss             : boss2026
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import os
import re
import sqlite3
import sys
import uuid
from functools import wraps

from flask import (
    Flask,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

# ----------------------------------------------------------------------------
# Optional heavy dependencies (the app degrades gracefully if missing)
# ----------------------------------------------------------------------------
try:
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill

    HAS_OPENPYXL = True
except ImportError:  # pragma: no cover
    HAS_OPENPYXL = False

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as pdf_canvas
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    HAS_REPORTLAB = True
except ImportError:  # pragma: no cover
    HAS_REPORTLAB = False


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("IKAWAL_DB", os.path.join(BASE_DIR, "ikawal.db"))

app = Flask(__name__)
app.secret_key = os.environ.get("IKAWAL_SECRET", "iringkawal-bpk-2026-dev-secret")
app.permanent_session_lifetime = dt.timedelta(minutes=30)

# ----------------------------------------------------------------------------
# Roles & credentials
# ----------------------------------------------------------------------------
ROLES = {
    "staff": {
        "label": "Staff Iringkawal",
        "icon": "\U0001f9d1\u200d\U0001f4bc",
        "can": {"upload": True, "add": True, "edit": True, "del": True, "export": True},
    },
    "penyelia": {
        "label": "Penyelia",
        "icon": "\U0001f441\ufe0f",
        "can": {"upload": False, "add": False, "edit": True, "del": False, "export": True},
    },
    "boss": {
        "label": "Boss",
        "icon": "\U0001f9d1\u200d\u2708\ufe0f",
        "can": {"upload": False, "add": False, "edit": False, "del": False, "export": True},
    },
}

_DEFAULT_PASSWORDS = {
    "staff": os.environ.get("IKAWAL_PW_STAFF", "staff2026"),
    "penyelia": os.environ.get("IKAWAL_PW_PENYELIA", "penyelia2026"),
    "boss": os.environ.get("IKAWAL_PW_BOSS", "boss2026"),
}
PASSWORD_HASHES = {role: generate_password_hash(pw) for role, pw in _DEFAULT_PASSWORDS.items()}

BLN = [
    "Januari", "Februari", "Mac", "April", "Mei", "Jun",
    "Julai", "Ogos", "September", "Oktober", "November", "Disember",
]

REC_FIELDS = [
    "nama", "jantina", "umur", "bangsa", "warganegara", "jenis_kesalahan",
    "nombor_reman", "nombor_fail", "depot", "pegawai", "tarikh_tamat_reman",
    "tindakan", "surat_rayuan", "tarikh_dibebaskan", "cara_bebas",
    "tarikh_masuk", "dokumen", "catatan",
]

# Location of the bundled real dataset (imported automatically on first run).
DATASET_PATH = os.environ.get(
    "IKAWAL_DATASET", os.path.join(BASE_DIR, "data", "iringkawal_bpk2026.xlsx")
)


# ============================================================================
# Database
# ============================================================================
def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = sqlite3.connect(DB_PATH)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS records (
            id TEXT PRIMARY KEY,
            nama TEXT, jantina TEXT, umur INTEGER, bangsa TEXT, warganegara TEXT,
            jenis_kesalahan TEXT, nombor_reman TEXT, nombor_fail TEXT, depot TEXT,
            pegawai TEXT, tarikh_tamat_reman TEXT, tindakan TEXT, surat_rayuan TEXT,
            tarikh_dibebaskan TEXT, cara_bebas TEXT,
            tarikh_masuk TEXT, dokumen TEXT, catatan TEXT,
            created_at TEXT, updated_at TEXT
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT, user TEXT, role TEXT, action TEXT, detail TEXT
        )
        """
    )
    # lightweight migration for databases created before these columns existed
    existing = {row[1] for row in db.execute("PRAGMA table_info(records)")}
    for col in ("tarikh_masuk", "dokumen", "catatan"):
        if col not in existing:
            db.execute(f"ALTER TABLE records ADD COLUMN {col} TEXT")
    db.commit()
    count = db.execute("SELECT COUNT(*) FROM records").fetchone()[0]
    if count == 0:
        loaded = load_dataset_into(db)
        if not loaded:
            for rec in sample_records():
                _insert_record(db, rec)
            action, detail = "Seed", "Data contoh dimuatkan"
        else:
            action, detail = "Seed", f"Set data diimport ({loaded} rekod)"
        db.execute(
            "INSERT INTO audit (ts, user, role, action, detail) VALUES (?,?,?,?,?)",
            (now_ts(), "system", "Sistem", action, detail),
        )
        db.commit()
    db.close()


def load_dataset_into(db: sqlite3.Connection) -> int:
    """Import the bundled Excel/CSV dataset if available. Returns row count."""
    path = DATASET_PATH
    if not path or not os.path.exists(path):
        return 0
    try:
        if path.lower().endswith(".csv"):
            with open(path, "rb") as fh:
                rows = parse_csv_bytes(fh.read())
        else:
            if not HAS_OPENPYXL:
                return 0
            wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
            ws = wb[wb.sheetnames[0]]
            rows = [list(r) for r in ws.iter_rows(values_only=True)]
    except Exception:  # noqa: BLE001
        return 0
    records, _report = clean_rows(rows)
    for rec in records:
        rec["id"] = "r" + uuid.uuid4().hex[:10]
        _insert_record(db, rec)
    db.commit()
    return len(records)


def now_ts() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _insert_record(db: sqlite3.Connection, rec: dict) -> None:
    cols = REC_FIELDS + ["id", "created_at", "updated_at"]
    values = [rec.get(f) for f in REC_FIELDS] + [
        rec["id"],
        rec.get("created_at") or now_ts(),
        now_ts(),
    ]
    placeholders = ",".join("?" for _ in cols)
    db.execute(
        f"INSERT INTO records ({','.join(cols)}) VALUES ({placeholders})", values
    )


def row_to_dict(row: sqlite3.Row) -> dict:
    d = {k: row[k] for k in row.keys()}
    if d.get("umur") is None:
        d["umur"] = ""
    for f in REC_FIELDS:
        if d.get(f) is None:
            d[f] = ""
    return d


# ============================================================================
# Audit
# ============================================================================
def audit(action: str, detail: str = "") -> None:
    if "db" not in g:
        return
    user = session.get("name", "-")
    role = ROLES.get(session.get("role"), {}).get("label", "-")
    g.db.execute(
        "INSERT INTO audit (ts, user, role, action, detail) VALUES (?,?,?,?,?)",
        (now_ts(), user, role, action, detail or ""),
    )
    # keep only the most recent 400 entries
    g.db.execute(
        "DELETE FROM audit WHERE id NOT IN "
        "(SELECT id FROM audit ORDER BY id DESC LIMIT 400)"
    )
    g.db.commit()


# ============================================================================
# Auth helpers
# ============================================================================
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("role"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "unauthenticated"}), 401
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def current_user() -> dict:
    role = session.get("role")
    if not role or role not in ROLES:
        return {"authenticated": False, "role": None, "name": None, "can": {}}
    return {
        "authenticated": True,
        "role": role,
        "label": ROLES[role]["label"],
        "icon": ROLES[role]["icon"],
        "name": session.get("name") or ROLES[role]["label"],
        "can": ROLES[role]["can"],
    }


def can(act: str) -> bool:
    return bool(ROLES.get(session.get("role"), {}).get("can", {}).get(act))


# ============================================================================
# Auto-clean engine (ported from app.html)
# ============================================================================
def norm_key(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str("" if s is None else s).lower())


def title_case(s) -> str:
    return re.sub(
        r"\b([a-z])", lambda m: m.group(1).upper(),
        str("" if s is None else s).lower(),
    ).strip()


def detect_field(h):
    n = norm_key(h)
    if not n:
        return None

    def has_any(keys):
        return any(k in n for k in keys)

    if has_any(["pegawai", "officer", "handle", "penyelia"]):
        return "pegawai"
    if "dokumen" in n or "document" in n:
        return "dokumen"
    if has_any(["catatan", "nota", "remark", "note"]):
        return "catatan"
    if "dibebas" in n:
        return "tarikh_dibebaskan"
    if "bebas" in n and "cara" in n:
        return "cara_bebas"
    if "masuk" in n and "tarikh" in n:
        return "tarikh_masuk"
    if "tarikh" in n and "reman" in n:
        return "tarikh_tamat_reman"
    if "tamat" in n:
        return "tarikh_tamat_reman"
    if "tarikh" in n:
        return "tarikh_tamat_reman"
    if "rayuan" in n:
        return "surat_rayuan"
    if "tindakan" in n:
        return "tindakan"
    if "fail" in n:
        return "nombor_fail"
    if "reman" in n:
        return "nombor_reman"
    if has_any(["depot", "lokasi", "cawangan", "balai"]):
        return "depot"
    if has_any(["kesalahan", "offence", "kes"]):
        return "jenis_kesalahan"
    if has_any(["bangsa", "race", "keturunan", "etnik"]) and has_any(
        ["warganegara", "nationality", "negara", "kewarganegaraan"]
    ):
        return "bangsa_warganegara"
    if has_any(["bangsa", "race", "keturunan", "etnik"]):
        return "bangsa"
    if has_any(["warganegara", "nationality", "kewarganegaraan"]):
        return "warganegara"
    if has_any(["jantina", "gender", "sex", "jk"]) and has_any(["umur", "age", "usia"]):
        return "jantina_umur"
    if has_any(["jantina", "gender", "sex", "jk"]):
        return "jantina"
    if has_any(["umur", "age", "usia"]):
        return "umur"
    if "nama" in n:
        return "nama"
    return None


def norm_jantina(v) -> str:
    s = str("" if v is None else v).lower()
    if re.search(r"perempuan|female|wanita|^p$|^f$|\bp\b", s):
        return "Perempuan"
    if re.search(r"lelaki|male|jantan|^l$|^m$|\bl\b", s):
        return "Lelaki"
    return ""


def clean_umur(v):
    if v is None or v == "":
        return ""
    m = re.search(r"(\d{1,3})", str(v))
    return int(m.group(1)) if m else ""


def norm_bangsa(v) -> str:
    s = title_case(v)
    if not s:
        return ""
    low = s.lower()
    for key, out in [
        ("melayu", "Melayu"), ("cina", "Cina"), ("chin", "Cina"),
        ("india", "India"), ("indian", "India"), ("bajau", "Bajau"),
        ("kadazan", "Kadazan"), ("dusun", "Dusun"),
        ("indonesia", "Indonesia"), ("filipin", "Filipina"),
    ]:
        if key in low:
            return out
    return s


def norm_negara(v) -> str:
    s = title_case(v)
    if not s:
        return ""
    low = s.lower()
    for key, out in [
        ("malaysia", "Malaysia"), ("indonesia", "Indonesia"), ("filipin", "Filipina"),
    ]:
        if key in low:
            return out
    return s


def split_bw(raw, rep) -> dict:
    s = str("" if raw is None else raw)
    parts = [p.strip() for p in re.split(r"[/|,\u2013\u2014-]+", s) if p.strip()]
    bangsa = negara = ""
    if len(parts) >= 2:
        a = norm_bangsa(parts[0])
        b = norm_negara(parts[1])
        a_is_nat = bool(re.match(r"^(malaysia|indonesia|filipina)$", a, re.I))
        bangsa = b if a_is_nat else a
        negara = a if a_is_nat else b
        rep["bw_split"] += 1
    else:
        one = parts[0] if parts else ""
        if re.match(r"^(malaysia|indonesia|filipina|malaysian|indonesian|filipino)$", one.strip(), re.I):
            negara = norm_negara(one)
        else:
            bangsa = norm_bangsa(one)
    return {"bangsa": bangsa, "warganegara": negara}


def split_ga(raw, rep) -> dict:
    s = str("" if raw is None else raw)
    if re.search(r"thn|tahun", s, re.I):
        rep["thn_removed"] += 1
    j = norm_jantina(s)
    u = clean_umur(s)
    if j or u != "":
        rep["ga_split"] += 1
    return {"jantina": j, "umur": u}


def norm_depot(v) -> str:
    s = str("" if v is None else v).lower()
    if "papar" in s or s.strip() == "dip":
        return "Papar"
    if "kinabalu" in s or "kk" in s or s.strip() == "dikk":
        return "Kota Kinabalu"
    return title_case(v)


def norm_tindakan(v) -> str:
    s = str("" if v is None else v).lower()
    if "usir" in s or s.strip() in ("usi", "usr"):
        return "Usir"
    if "sambung" in s:
        return "Sambung Reman"
    if "bebas" in s or "lepas" in s:
        return "Bebas"
    if "tuduh" in s or "mahkamah" in s:
        return "Tuduh di Mahkamah"
    if "agensi" in s:
        return "Hantar Agensi Lain"
    return title_case(v)


def norm_rayuan(v) -> str:
    s = str("" if v is None else v).lower()
    if "terima" in s:
        return "Diterima"
    if "semak" in s:
        return "Dalam Semakan"
    if "tiada" in s or "tidak" in s or "none" in s or s == "":
        return "Tiada"
    return title_case(v)


def norm_cara_bebas(v) -> str:
    s = str("" if v is None else v).lower()
    if "tanpa" in s:
        return "Bebas Tanpa Syarat"
    if "jamin" in s:
        return "Bebas Dengan Jaminan"
    if "mahkamah" in s or "perintah" in s:
        return "Bebas Atas Perintah Mahkamah"
    return title_case(v)


def to_iso_date(v) -> str:
    if v is None or v == "":
        return ""
    if isinstance(v, dt.datetime):
        return v.date().isoformat()
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        try:
            days = float(v) - 25569
            d = dt.datetime(1970, 1, 1) + dt.timedelta(days=days)
            return d.date().isoformat()
        except Exception:
            return ""
    s = str(v).strip()
    m = re.match(r"^(\d{4})[./-](\d{1,2})[./-](\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.match(r"^(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})", s)
    if m:
        y = m.group(3)
        y = ("20" + y) if len(y) == 2 else y
        return f"{y}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return ""


def clean_rows(rows: list[list]) -> tuple[list[dict], dict]:
    rep = {
        "total": 0, "thn_removed": 0, "ga_split": 0, "bw_split": 0,
        "dup": [], "date_empty": [], "mapped": [], "unmapped": [],
    }
    best_idx, best_score, best_map = 0, -1, []
    for i in range(min(len(rows), 12)):
        r = rows[i] or []
        score, mp = 0, []
        for cell in r:
            f = detect_field(cell)
            mp.append(f)
            if f:
                score += 1
        if score > best_score:
            best_score, best_idx, best_map = score, i, mp
    if best_score <= 0:
        return [], rep

    headers = rows[best_idx] or []
    mp = best_map
    for idx, h in enumerate(headers):
        f = mp[idx] if idx < len(mp) else None
        if f:
            rep["mapped"].append(f"{h} -> {f}")
        elif str(h).strip():
            rep["unmapped"].append(str(h))

    records: list[dict] = []
    for k in range(best_idx + 1, len(rows)):
        row = rows[k] or []
        if all(c == "" or c is None for c in row):
            continue
        rec = {f: "" for f in REC_FIELDS}
        for c in range(len(mp)):
            f = mp[c]
            if not f:
                continue
            raw = row[c] if c < len(row) else ""
            if raw is None:
                raw = ""
            if f == "jantina_umur":
                res = split_ga(raw, rep)
                if res["jantina"]:
                    rec["jantina"] = res["jantina"]
                if res["umur"] != "":
                    rec["umur"] = res["umur"]
            elif f == "bangsa_warganegara":
                res = split_bw(raw, rep)
                if res["bangsa"]:
                    rec["bangsa"] = res["bangsa"]
                if res["warganegara"]:
                    rec["warganegara"] = res["warganegara"]
            elif f == "umur":
                if re.search(r"thn|tahun", str(raw), re.I):
                    rep["thn_removed"] += 1
                rec["umur"] = clean_umur(raw)
            elif f == "jantina":
                rec["jantina"] = norm_jantina(raw) or title_case(raw)
            elif f == "bangsa":
                rec["bangsa"] = norm_bangsa(raw)
            elif f == "warganegara":
                rec["warganegara"] = norm_negara(raw)
            elif f == "depot":
                rec["depot"] = norm_depot(raw)
            elif f == "tindakan":
                rec["tindakan"] = norm_tindakan(raw)
            elif f == "surat_rayuan":
                rec["surat_rayuan"] = norm_rayuan(raw)
            elif f == "tarikh_tamat_reman":
                rec["tarikh_tamat_reman"] = to_iso_date(raw)
            elif f == "tarikh_masuk":
                rec["tarikh_masuk"] = to_iso_date(raw)
            elif f == "tarikh_dibebaskan":
                rec["tarikh_dibebaskan"] = to_iso_date(raw)
            elif f == "cara_bebas":
                rec["cara_bebas"] = norm_cara_bebas(raw)
            elif f == "nama":
                rec["nama"] = str(raw).strip()
            else:
                rec[f] = str(raw).strip()

        if not rec["nama"] and not rec["nombor_fail"]:
            continue
        if rec["jantina"] not in ("Lelaki", "Perempuan"):
            rec["jantina"] = norm_jantina(rec["jantina"]) or rec["jantina"] or "Lelaki"
        if rec["depot"] not in ("Papar", "Kota Kinabalu"):
            rec["depot"] = norm_depot(rec["depot"]) or rec["depot"] or "Kota Kinabalu"
        if not rec["tindakan"]:
            rec["tindakan"] = "Sambung Reman"
        if not rec["surat_rayuan"]:
            rec["surat_rayuan"] = "Tiada"
        if rec["tindakan"] != "Bebas":
            rec["tarikh_dibebaskan"] = ""
            rec["cara_bebas"] = ""
        if rec["umur"] == "":
            rec["umur"] = None
        records.append(rec)

    rep["total"] = len(records)
    counts: dict[str, int] = {}
    for r in records:
        key = dup_key(r)
        if key:
            counts[key] = counts.get(key, 0) + 1
    for key, n in counts.items():
        if n > 1:
            rep["dup"].append({"ref": key, "count": n})
    for r in records:
        if not r["tarikh_tamat_reman"]:
            rep["date_empty"].append(r["nama"] or "(tiada nama)")
    return records, rep


# ============================================================================
# Computed helpers
# ============================================================================
def today_date() -> dt.date:
    return dt.date.today()


def days_left(rec: dict):
    iso = rec.get("tarikh_tamat_reman")
    if not iso:
        return None
    try:
        d = dt.date.fromisoformat(iso)
    except ValueError:
        return None
    return (d - today_date()).days


def is_bebas(rec: dict) -> bool:
    return bool(rec.get("tarikh_dibebaskan"))


def status_semasa(rec: dict) -> str:
    return "SUDAH BEBAS" if is_bebas(rec) else "DALAM TAHANAN"


def is_urgent(rec: dict) -> bool:
    if is_bebas(rec):
        return False
    dl = days_left(rec)
    return dl is not None and dl <= 3


def has_rayuan(rec: dict) -> bool:
    return rec.get("surat_rayuan") in ("Diterima", "Dalam Semakan")


def dup_key(rec: dict) -> str:
    """Reference used for duplicate detection: the reman number, falling back
    to name + file number when the reman number is missing."""
    reman = (rec.get("nombor_reman") or "").strip().upper()
    if reman:
        return reman
    nama = (rec.get("nama") or "").strip().upper()
    fail = (rec.get("nombor_fail") or "").strip().upper()
    return f"{nama}|{fail}" if (nama or fail) else ""


def filtered_records(records, f_filter, f_search, f_officer, f_sort):
    def keep(r):
        if f_officer and ((r.get("pegawai") or "").strip() or "(Tiada Pegawai)") != f_officer:
            return False
        if f_filter == "urgent" and not is_urgent(r):
            return False
        if f_filter == "papar" and r.get("depot") != "Papar":
            return False
        if f_filter == "kk" and r.get("depot") != "Kota Kinabalu":
            return False
        if f_filter == "rayuan" and not has_rayuan(r):
            return False
        if f_filter == "bebas" and not is_bebas(r):
            return False
        if f_search:
            hay = " ".join(
                str(r.get(k) or "")
                for k in ("nama", "nombor_fail", "nombor_reman", "pegawai", "bangsa",
                          "jenis_kesalahan", "depot", "warganegara")
            ).lower()
            if f_search.lower() not in hay:
                return False
        return True

    out = [r for r in records if keep(r)]

    if f_sort == "nama":
        out.sort(key=lambda r: str(r.get("nama") or "").lower())
    elif f_sort == "pegawai":
        out.sort(key=lambda r: (str(r.get("pegawai") or "").lower(),
                                str(r.get("nama") or "").lower()))
    elif f_sort == "depot":
        out.sort(key=lambda r: (str(r.get("depot") or "").lower(),
                                str(r.get("nama") or "").lower()))
    else:
        out.sort(key=lambda r: (days_left(r) is None,
                                days_left(r) if days_left(r) is not None else 0))
    return out


def officer_stats(records):
    m: dict[str, int] = {}
    for r in records:
        k = (r.get("pegawai") or "").strip() or "(Tiada Pegawai)"
        m[k] = m.get(k, 0) + 1
    arr = [{"name": k, "count": v} for k, v in m.items()]
    arr.sort(key=lambda o: (-o["count"], o["name"].lower()))
    return arr


def count_by(records, key):
    m: dict[str, int] = {}
    for r in records:
        v = r.get(key) or "-"
        m[v] = m.get(v, 0) + 1
    return m


def dup_set(records):
    counts: dict[str, int] = {}
    for r in records:
        k = dup_key(r)
        if k:
            counts[k] = counts.get(k, 0) + 1
    return {k for k, n in counts.items() if n > 1}


# ============================================================================
# Period filtering (for reports)
# ============================================================================
def add_days(d: dt.date, n: int) -> dt.date:
    return d + dt.timedelta(days=n)


def period_records(records, period):
    if not period or period == "semua":
        return list(records)
    t = today_date()
    frm = to = None
    if period == "7":
        frm, to = t, add_days(t, 7)
    elif period == "30":
        frm, to = t, add_days(t, 30)
    elif period == "bulan":
        frm = t.replace(day=1)
        nxt = (frm + dt.timedelta(days=32)).replace(day=1)
        to = nxt - dt.timedelta(days=1)
    elif period == "tamat":
        to = add_days(t, -1)

    def keep(r):
        iso = r.get("tarikh_tamat_reman")
        if not iso:
            return False
        try:
            d = dt.date.fromisoformat(iso)
        except ValueError:
            return False
        if frm and d < frm:
            return False
        if to and d > to:
            return False
        return True

    out = [r for r in records if keep(r)]
    out.sort(key=lambda r: r.get("tarikh_tamat_reman") or "")
    return out


PERIOD_LABELS = {
    "semua": "Semua rekod",
    "7": "Mingguan \u00b7 7 hari akan datang",
    "30": "Bulanan \u00b7 30 hari akan datang",
    "bulan": "Bulan kalendar semasa",
    "tamat": "Sudah tamat reman",
}


def period_label(period: str) -> str:
    return PERIOD_LABELS.get(period, "Semua rekod")


# ============================================================================
# Sample data
# ============================================================================
def sample_records():
    today = today_date()

    def iso(off):
        return add_days(today, off).isoformat()

    raw = [
        ("Ahmad bin Abdullah", "Lelaki", 34, "Melayu", "Malaysia", "Kes Curi", "RMN/2026/001", "BPK/KK/2026/0145", "Kota Kinabalu", "Insp. Ahmad", 2, "Sambung Reman", "Diterima", None, ""),
        ("Siti Nurhaliza binti Omar", "Perempuan", 28, "Bajau", "Malaysia", "Kes Dadah", "RMN/2026/002", "BPK/PPR/2026/0089", "Papar", "Sgt. Siti", 1, "Tuduh di Mahkamah", "Dalam Semakan", None, ""),
        ("Lim Wei Jie", "Lelaki", 41, "Cina", "Malaysia", "Kes Bunuh", "RMN/2026/003", "BPK/PPR/2026/0093", "Papar", "Kpl. John", -1, "Bebas", "Tiada", -2, "Bebas Dengan Jaminan"),
        ("Rajesh a/l Kumar", "Lelaki", 37, "India", "Malaysia", "Kes Rogol", "RMN/2026/004", "BPK/KK/2026/0151", "Kota Kinabalu", "Insp. Ahmad", 5, "Sambung Reman", "Tiada", None, ""),
        ("Budi Santoso", "Lelaki", 45, "Indonesia", "Indonesia", "Kes Pendatang Asing", "RMN/2026/005", "BPK/KK/2026/0158", "Kota Kinabalu", "Insp. Ahmad", 6, "Hantar Agensi Lain", "Dalam Semakan", None, ""),
        ("Maria Santos", "Perempuan", 31, "Filipina", "Filipina", "Kes Dadah", "RMN/2026/006", "BPK/PPR/2026/0101", "Papar", "Sgt. Siti", 9, "Tuduh di Mahkamah", "Diterima", None, ""),
        ("Tan Mei Ling", "Perempuan", 26, "Cina", "Malaysia", "Kes Curi", "RMN/2026/007", "BPK/KK/2026/0163", "Kota Kinabalu", "Insp. Ahmad", 1, "Sambung Reman", "Tiada", None, ""),
        ("Mohd Faizal bin Hassan", "Lelaki", 33, "Melayu", "Malaysia", "Kes Samun", "RMN/2026/008", "BPK/PPR/2026/0110", "Papar", "Sgt. Siti", 14, "Tuduh di Mahkamah", "Tiada", None, ""),
        ("Priya a/p Samy", "Perempuan", 29, "India", "Malaysia", "Kes Penipuan", "RMN/2026/009", "BPK/KK/2026/0171", "Kota Kinabalu", "Insp. Ahmad", 2, "Sambung Reman", "Dalam Semakan", None, ""),
        ("Juan Dela Cruz", "Lelaki", 39, "Filipina", "Filipina", "Kes Pendatang Asing", "RMN/2026/010", "BPK/PPR/2026/0118", "Papar", "Kpl. John", 21, "Hantar Agensi Lain", "Tiada", None, ""),
        ("Dewi Lestari", "Perempuan", 35, "Indonesia", "Indonesia", "Kes Dadah", "RMN/2026/011", "BPK/PPR/2026/0120", "Papar", "Sgt. Siti", 4, "Bebas", "Diterima", -6, "Bebas Tanpa Syarat"),
        ("Nurul Aisyah binti Rahim", "Perempuan", 24, "Melayu", "Malaysia", "Kes Curi", "RMN/2026/012", "BPK/KK/2026/0180", "Kota Kinabalu", "Kpl. John", 7, "Tuduh di Mahkamah", "Tiada", None, ""),
    ]
    out = []
    for r in raw:
        out.append({
            "id": "r" + uuid.uuid4().hex[:10],
            "nama": r[0], "jantina": r[1], "umur": r[2], "bangsa": r[3],
            "warganegara": r[4], "jenis_kesalahan": r[5], "nombor_reman": r[6],
            "nombor_fail": r[7], "depot": r[8], "pegawai": r[9],
            "tarikh_tamat_reman": iso(r[10]), "tindakan": r[11],
            "surat_rayuan": r[12],
            "tarikh_dibebaskan": iso(r[13]) if r[13] is not None else "",
            "cara_bebas": r[14] or "",
        })
    return out


# ============================================================================
# Routes: auth & pages
# ============================================================================
@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        role = (request.form.get("role") or "staff").strip()
        name = (request.form.get("name") or "").strip()
        password = request.form.get("password") or ""
        if role not in ROLES:
            role = "staff"
        if check_password_hash(PASSWORD_HASHES[role], password):
            session.permanent = True
            session["role"] = role
            session["name"] = name or ROLES[role]["label"]
            audit("Log masuk", ROLES[role]["label"])
            return redirect(url_for("index"))
        error = f"Kata laluan salah untuk {ROLES[role]['label']}."
    return render_template("login.html", roles=ROLES, error=error)


@app.route("/logout")
def logout():
    if session.get("role"):
        audit("Log keluar", ROLES.get(session["role"], {}).get("label", "-"))
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template("index.html", user=current_user())


@app.route("/app")
@login_required
def app_shell():
    """Serve the single-file app.html, wired to this JSON API."""
    return send_from_directory(BASE_DIR, "app.html")


@app.route("/app.html")
def app_html_alias():
    return redirect(url_for("app_shell") if session.get("role") else url_for("login"))


# ============================================================================
# Routes: API
# ============================================================================
@app.route("/api/me")
@login_required
def api_me():
    return jsonify(current_user())


@app.route("/api/data")
@login_required
def api_data():
    db = get_db()
    rows = [row_to_dict(r) for r in db.execute("SELECT * FROM records ORDER BY created_at").fetchall()]
    records = rows

    # --- merge in SmartDepot engine results (UC-2/3/4) ---
    engine = {"by_risk": {}, "alerts": [], "alert_count": 0, "critical": 0, "high": 0}
    try:
        from smartdepot.bridge import engine_bundle

        bundle = engine_bundle(records)
        for r in records:
            r.update(bundle["by_id"].get(r.get("id"), {}))
        engine = bundle["panel"]
    except Exception as exc:  # noqa: BLE001  (engines are optional)
        engine = {"error": str(exc), "by_risk": {}, "alerts": [],
                  "alert_count": 0, "critical": 0, "high": 0}

    f_filter = request.args.get("filter", "semua")
    f_search = request.args.get("q", "")
    f_officer = request.args.get("officer") or None
    f_sort = request.args.get("sort", "tarikh")

    listed = filtered_records(records, f_filter, f_search, f_officer, f_sort)

    active = [r for r in records if not is_bebas(r)]
    stats = {
        "total": len(active),
        "lelaki": sum(1 for r in active if r["jantina"] == "Lelaki"),
        "perempuan": sum(1 for r in active if r["jantina"] == "Perempuan"),
        "papar": sum(1 for r in active if r["depot"] == "Papar"),
        "kk": sum(1 for r in active if r["depot"] == "Kota Kinabalu"),
        "urgent": sum(1 for r in active if is_urgent(r)),
        "bebas": sum(1 for r in records if is_bebas(r)),
        "total_all": len(records),
    }
    counts = {
        "semua": len(records),
        "urgent": sum(1 for r in records if is_urgent(r)),
        "papar": sum(1 for r in records if r["depot"] == "Papar"),
        "kk": sum(1 for r in records if r["depot"] == "Kota Kinabalu"),
        "rayuan": sum(1 for r in records if has_rayuan(r)),
        "bebas": sum(1 for r in records if is_bebas(r)),
    }
    return jsonify({
        "records": listed,
        "all_count": len(records),
        "stats": stats,
        "counts": counts,
        "officers": officer_stats(records),
        "engine": engine,
        "charts": {
            "jantina": count_by(records, "jantina"),
            "bangsa": count_by(records, "bangsa"),
            "depot": count_by(records, "depot"),
            "kesalahan": count_by(records, "jenis_kesalahan"),
        },
        "dup": sorted(dup_set(records)),
    })


@app.route("/api/records", methods=["POST"])
@login_required
def api_create_record():
    if not can("add"):
        return jsonify({"error": "Tiada akses tambah rekod."}), 403
    data = request.get_json(silent=True) or {}
    rec = normalize_payload(data)
    if not rec["nama"]:
        return jsonify({"error": "Sila isi Nama."}), 400
    if not (rec["nombor_fail"] or rec["nombor_reman"]):
        return jsonify({"error": "Sila isi Nombor Reman atau Nombor Fail."}), 400
    if rec["tindakan"] == "Bebas" and not rec["tarikh_dibebaskan"]:
        return jsonify({"error": "Sila isi Tarikh Dibebaskan untuk tindakan Bebas."}), 400
    rec["id"] = "r" + uuid.uuid4().hex[:10]
    _insert_record(get_db(), rec)
    get_db().commit()
    audit("Tambah rekod", rec["nama"])
    return jsonify({"ok": True, "id": rec["id"]})


@app.route("/api/records/<rid>", methods=["PUT", "PATCH"])
@login_required
def api_update_record(rid):
    if not can("edit"):
        return jsonify({"error": "Tiada akses edit."}), 403
    data = request.get_json(silent=True) or {}
    rec = normalize_payload(data)
    if not rec["nama"]:
        return jsonify({"error": "Sila isi Nama."}), 400
    if not (rec["nombor_fail"] or rec["nombor_reman"]):
        return jsonify({"error": "Sila isi Nombor Reman atau Nombor Fail."}), 400
    if rec["tindakan"] == "Bebas" and not rec["tarikh_dibebaskan"]:
        return jsonify({"error": "Sila isi Tarikh Dibebaskan untuk tindakan Bebas."}), 400
    db = get_db()
    exists = db.execute("SELECT id FROM records WHERE id=?", (rid,)).fetchone()
    if not exists:
        return jsonify({"error": "Rekod tidak dijumpai."}), 404
    sets = ",".join(f"{f}=?" for f in REC_FIELDS)
    values = [rec[f] for f in REC_FIELDS] + [now_ts(), rid]
    db.execute(f"UPDATE records SET {sets}, updated_at=? WHERE id=?", values)
    db.commit()
    audit("Edit rekod", rec["nama"])
    return jsonify({"ok": True})


@app.route("/api/records/<rid>", methods=["DELETE"])
@login_required
def api_delete_record(rid):
    if not can("del"):
        return jsonify({"error": "Tiada akses padam."}), 403
    db = get_db()
    row = db.execute("SELECT nama FROM records WHERE id=?", (rid,)).fetchone()
    if not row:
        return jsonify({"error": "Rekod tidak dijumpai."}), 404
    db.execute("DELETE FROM records WHERE id=?", (rid,))
    db.commit()
    audit("Padam rekod", row["nama"])
    return jsonify({"ok": True})


@app.route("/api/records", methods=["DELETE"])
@login_required
def api_clear_records():
    if not can("del"):
        return jsonify({"error": "Tiada akses padam."}), 403
    db = get_db()
    db.execute("DELETE FROM records")
    db.commit()
    audit("Padam semua data", "")
    return jsonify({"ok": True})


@app.route("/api/sample", methods=["POST"])
@login_required
def api_sample():
    if not can("upload"):
        return jsonify({"error": "Peranan anda tiada akses muat naik."}), 403
    db = get_db()
    db.execute("DELETE FROM records")
    for rec in sample_records():
        _insert_record(db, rec)
    db.commit()
    audit("Guna data contoh", "12 rekod")
    return jsonify({"ok": True, "count": 12})


def normalize_payload(data: dict) -> dict:
    def s(key):
        v = data.get(key)
        return "" if v is None else str(v).strip()

    umur = data.get("umur")
    if umur in ("", None):
        umur_val = None
    else:
        try:
            umur_val = int(re.search(r"\d+", str(umur)).group())
        except (AttributeError, ValueError):
            umur_val = None

    rec = {
        "nama": s("nama"),
        "jantina": s("jantina") or "Lelaki",
        "umur": umur_val,
        "bangsa": s("bangsa"),
        "warganegara": s("warganegara"),
        "jenis_kesalahan": s("jenis_kesalahan"),
        "nombor_reman": s("nombor_reman"),
        "nombor_fail": s("nombor_fail"),
        "depot": s("depot") or "Papar",
        "pegawai": s("pegawai"),
        "tarikh_tamat_reman": to_iso_date(s("tarikh_tamat_reman")),
        "tindakan": norm_tindakan(s("tindakan")) or "Sambung Reman",
        "surat_rayuan": s("surat_rayuan") or "Tiada",
        "tarikh_dibebaskan": "",
        "cara_bebas": "",
        "tarikh_masuk": to_iso_date(s("tarikh_masuk")),
        "dokumen": s("dokumen"),
        "catatan": s("catatan"),
    }
    if rec["tindakan"] == "Bebas":
        rec["tarikh_dibebaskan"] = to_iso_date(s("tarikh_dibebaskan"))
        rec["cara_bebas"] = s("cara_bebas") or "Bebas Tanpa Syarat"
    if rec["jantina"] not in ("Lelaki", "Perempuan"):
        rec["jantina"] = norm_jantina(rec["jantina"]) or "Lelaki"
    return rec


# ----------------------------------------------------------------------------
# Import
# ----------------------------------------------------------------------------
def parse_csv_bytes(data: bytes):
    text = data.decode("utf-8-sig", errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    first = lines[0] if lines else ""
    delim = ";" if first.count(";") > first.count(",") else ","
    return [row for row in csv.reader(io.StringIO(text), delimiter=delim)]


@app.route("/api/import", methods=["POST"])
@login_required
def api_import():
    if not can("upload"):
        return jsonify({"error": "Peranan anda tiada akses muat naik."}), 403
    up = request.files.get("file")
    if not up or not up.filename:
        return jsonify({"error": "Tiada fail dimuat naik."}), 400
    name = up.filename.lower()
    data = up.read()
    try:
        if name.endswith(".csv"):
            rows = parse_csv_bytes(data)
        else:
            if not HAS_OPENPYXL:
                return jsonify({"error": "Pustaka openpyxl tidak dipasang."}), 500
            wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
            ws = wb[wb.sheetnames[0]]
            rows = [list(r) for r in ws.iter_rows(values_only=True)]
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Gagal membaca fail: {exc}"}), 400

    records, report = clean_rows(rows)
    if not records:
        return jsonify({"error": "Tiada data sah ditemui dalam fail."}), 400

    db = get_db()
    db.execute("DELETE FROM records")
    for rec in records:
        rec["id"] = "r" + uuid.uuid4().hex[:10]
        _insert_record(db, rec)
    db.commit()
    audit("Muat naik fail", f"{up.filename} \u00b7 {len(records)} rekod")
    return jsonify({"ok": True, "count": len(records), "report": report})


# ----------------------------------------------------------------------------
# Export: Excel
# ----------------------------------------------------------------------------
@app.route("/api/export/xlsx")
@login_required
def api_export_xlsx():
    if not can("export"):
        return jsonify({"error": "Peranan anda tiada akses eksport."}), 403
    if not HAS_OPENPYXL:
        return jsonify({"error": "Pustaka openpyxl tidak dipasang."}), 500
    db = get_db()
    records = [row_to_dict(r) for r in db.execute("SELECT * FROM records ORDER BY created_at").fetchall()]

    headers = [
        "Nama", "Jantina", "Umur", "Bangsa", "Warganegara", "Jenis Kesalahan",
        "Nombor Reman", "Nombor Fail", "Depot", "Pegawai Handle",
        "Tarikh Masuk", "Tarikh Tamat Reman", "Tindakan Selepas Reman", "Status Semasa",
        "Tarikh Dibebaskan", "Cara Bebas", "Surat Rayuan", "Dokumen", "Catatan",
    ]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Tahanan Bersih"
    ws.append(headers)
    head_fill = PatternFill("solid", fgColor="12305F")
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = head_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for r in records:
        ws.append([
            r["nama"], r["jantina"], r["umur"], r["bangsa"], r["warganegara"],
            r["jenis_kesalahan"], r["nombor_reman"], r["nombor_fail"], r["depot"],
            r["pegawai"], r["tarikh_masuk"], r["tarikh_tamat_reman"], r["tindakan"],
            status_semasa(r), r["tarikh_dibebaskan"], r["cara_bebas"], r["surat_rayuan"],
            r["dokumen"], r["catatan"],
        ])
    widths = [26, 10, 6, 12, 13, 20, 16, 20, 16, 16, 12, 18, 22, 16, 18, 24, 16, 16, 30]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    audit("Eksport Excel", f"{len(records)} rekod")
    filename = f"Iringkawal_Bersih_{dt.datetime.now():%Y%m%d_%H%M}.xlsx"
    return send_file(
        buf, as_attachment=True, download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ----------------------------------------------------------------------------
# Export: PDF
# ----------------------------------------------------------------------------
@app.route("/api/export/pdf")
@login_required
def api_export_pdf():
    if not can("export"):
        return jsonify({"error": "Peranan anda tiada akses eksport."}), 403
    if not HAS_REPORTLAB:
        return jsonify({"error": "Pustaka reportlab tidak dipasang."}), 500
    period = request.args.get("period", "semua")
    db = get_db()
    records = [row_to_dict(r) for r in db.execute("SELECT * FROM records ORDER BY created_at").fetchall()]
    subset = period_records(records, period)
    if not subset:
        return jsonify({"error": "Tiada rekod dalam tempoh dipilih."}), 400

    pdf_bytes = build_pdf(subset, period_label(period))
    audit("Jana Laporan PDF", f"{period_label(period)} \u00b7 {len(subset)} rekod")
    filename = f"Iringkawal_Laporan_{dt.datetime.now():%Y%m%d_%H%M}.pdf"
    return send_file(io.BytesIO(pdf_bytes), as_attachment=True,
                     download_name=filename, mimetype="application/pdf")


class _NumberedCanvas(pdf_canvas.Canvas):
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
            self._footer(total)
            super().showPage()
        super().save()

    def _footer(self, total):
        w = self._pagesize[0]
        self.setFont("Helvetica", 7.5)
        self.setFillColorRGB(0.51, 0.57, 0.65)
        self.drawString(34, 18, "Iringkawal Analyzer + Supervisor Dashboard \u00b7 BPK 2026")
        self.drawRightString(w - 34, 18, f"Halaman {self._pageNumber} / {total}")


def build_pdf(records: list[dict], label: str) -> bytes:
    buf = io.BytesIO()
    page = landscape(A4)
    doc = SimpleDocTemplate(
        buf, pagesize=page, leftMargin=34, rightMargin=34,
        topMargin=74, bottomMargin=30,
        title="Iringkawal Analyzer - Laporan",
    )
    W = page[0]
    story = []
    styles = getSampleStyleSheet()

    def draw_header(canv, _doc):
        canv.saveState()
        canv.setFillColorRGB(10 / 255, 30 / 255, 63 / 255)
        canv.rect(0, page[1] - 56, W, 56, stroke=0, fill=1)
        canv.setFillColorRGB(20 / 255, 200 / 255, 182 / 255)
        canv.rect(0, page[1] - 59, W, 3, stroke=0, fill=1)
        canv.setFillColorRGB(1, 1, 1)
        canv.setFont("Helvetica-Bold", 15)
        canv.drawString(34, page[1] - 28, "IRINGKAWAL ANALYZER \u2014 LAPORAN PEMANTAUAN FAIL")
        canv.setFont("Helvetica", 8.5)
        canv.setFillColorRGB(195 / 255, 212 / 255, 235 / 255)
        canv.drawString(34, page[1] - 45, f"Bahagian Pengurusan Kesalahan (BPK) \u00b7 2026  \u2014  {label}")
        canv.drawRightString(
            W - 34, page[1] - 45,
            "Dijana: " + dt.datetime.now().strftime("%d %B %Y %H:%M"),
        )
        canv.restoreState()

    # KPI boxes
    kpis = [
        ("Total Tahanan", len(records)),
        ("Lelaki", sum(1 for r in records if r["jantina"] == "Lelaki")),
        ("Perempuan", sum(1 for r in records if r["jantina"] == "Perempuan")),
        ("Depot Papar", sum(1 for r in records if r["depot"] == "Papar")),
        ("Depot Kota Kinabalu", sum(1 for r in records if r["depot"] == "Kota Kinabalu")),
        ("Reman < 3 Hari", sum(1 for r in records if is_urgent(r))),
    ]
    gap = 9
    bw = (W - 68 - gap * 5) / 6
    kpi_row = [TableCell(str(v), k.upper()) for k, v in kpis]
    kpi_tbl = Table([kpi_row], colWidths=[bw] * 6)
    kpi_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F5F8FC")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CED8E6")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CED8E6")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(kpi_tbl)
    story.append(Spacer(1, 16))

    # Officer workload
    offs = officer_stats(records)
    maxc = offs[0]["count"] if offs else 0
    story.append(Paragraph("BEBAN KERJA PEGAWAI", ParagraphStyle(
        "h", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10,
        textColor=colors.HexColor("#0A1E3F"))))
    story.append(Spacer(1, 6))
    off_data = [["Pegawai", "Jumlah Fail", "Peratus", "Catatan"]]
    for o in offs:
        pct = round(o["count"] / len(records) * 100) if records else 0
        off_data.append([o["name"], str(o["count"]), f"{pct}%",
                         "* Beban terbanyak" if o["count"] == maxc else ""])
    off_tbl = Table(off_data, colWidths=[240, 100, 90, 180])
    off_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#12305F")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CED8E6")),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFCFF")]),
    ]))
    story.append(off_tbl)
    story.append(Spacer(1, 16))

    # Records table
    story.append(Paragraph(f"SENARAI TAHANAN \u2014 {len(records)} REKOD", ParagraphStyle(
        "h2", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10,
        textColor=colors.HexColor("#0A1E3F"))))
    story.append(Spacer(1, 6))
    head = ["Nama", "Jantina", "Umur", "Bangsa", "Warganegara", "Jenis Kesalahan",
            "No. Reman", "No. Fail", "Depot", "Pegawai", "Tamat Reman", "Tindakan",
            "Status", "Rayuan"]
    body = [head]
    urgent_rows = set()
    for i, r in enumerate(records, start=1):
        body.append([
            r["nama"], r["jantina"], "-" if r["umur"] == "" else str(r["umur"]),
            r["bangsa"], r["warganegara"], r["jenis_kesalahan"], r["nombor_reman"],
            r["nombor_fail"], r["depot"], r["pegawai"],
            r["tarikh_tamat_reman"] or "-", r["tindakan"], status_semasa(r),
            r["surat_rayuan"],
        ])
        if is_urgent(r):
            urgent_rows.add(i)
    weights = [1.7, 0.7, 0.45, 0.85, 0.95, 1.3, 1.0, 1.2, 0.9, 1.0, 0.95, 1.1, 0.95, 0.85]
    total_w = sum(weights)
    avail = W - 68
    col_w = [avail * x / total_w for x in weights]
    rec_tbl = Table(body, colWidths=col_w, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A1E3F")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#DCE6F2")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFCFF")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for i in urgent_rows:
        style.append(("TEXTCOLOR", (0, i), (-1, i), colors.HexColor("#C03335")))
        style.append(("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"))
    rec_tbl.setStyle(TableStyle(style))
    story.append(rec_tbl)

    doc.build(story, onFirstPage=draw_header, onLaterPages=draw_header,
              canvasmaker=_NumberedCanvas)
    return buf.getvalue()


class TableCell:
    """Tiny helper that renders a KPI box as a nested table (supports colour)."""

    def __new__(cls, value, label):
        v = Paragraph(
            f'<font size="14" color="#0A1E3F"><b>{value}</b></font>',
            ParagraphStyle("v", fontName="Helvetica-Bold", alignment=1, fontSize=14),
        )
        l = Paragraph(
            f'<font size="6.3" color="#5C6E8A">{label}</font>',
            ParagraphStyle("l", fontName="Helvetica", alignment=1, fontSize=6.5),
        )
        tbl = Table([[v], [l]])
        tbl.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (0, 0), 0),
            ("BOTTOMPADDING", (0, 0), (0, 0), 0),
            ("TOPPADDING", (0, 1), (0, 1), 0),
            ("BOTTOMPADDING", (0, 1), (0, 1), 0),
        ]))
        return tbl


# ----------------------------------------------------------------------------
# Audit endpoints
# ----------------------------------------------------------------------------
@app.route("/api/audit")
@login_required
def api_audit():
    db = get_db()
    rows = db.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 400").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/audit", methods=["DELETE"])
@login_required
def api_audit_clear():
    if not can("del"):
        return jsonify({"error": "Peranan anda tiada akses kosongkan log."}), 403
    db = get_db()
    db.execute("DELETE FROM audit")
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/audit", methods=["POST"])
@login_required
def api_audit_add():
    data = request.get_json(silent=True) or {}
    audit(str(data.get("action") or ""), str(data.get("detail") or ""))
    return jsonify({"ok": True})


# ----------------------------------------------------------------------------
# CLI entry point
# ----------------------------------------------------------------------------
def reset_and_import() -> int:
    """Wipe records and re-import the bundled dataset (or sample fallback)."""
    init_db()
    db = sqlite3.connect(DB_PATH)
    db.execute("DELETE FROM records")
    db.commit()
    n = load_dataset_into(db)
    if not n:
        for rec in sample_records():
            _insert_record(db, rec)
        n = len(sample_records())
        note = "Data contoh"
    else:
        note = "Set data"
    db.execute(
        "INSERT INTO audit (ts, user, role, action, detail) VALUES (?,?,?,?,?)",
        (now_ts(), "system", "Sistem", "Reimport", f"{note} ({n} rekod)"),
    )
    db.commit()
    db.close()
    return n


# --- SmartDepot engines (UC-2/3/4) — optional, additive integration ---------
# Registered only if the `smartdepot` package and its deps are importable, so the
# Iringkawal app still runs on its own. Adds /engine and /api/engine/* routes.
try:  # pragma: no cover
    from smartdepot.flask_api import engine_bp  # type: ignore

    app.register_blueprint(engine_bp)
except Exception as _engine_exc:  # noqa: BLE001
    print(f"[smartdepot] engines not loaded: {_engine_exc}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("import", "reimport", "load"):
        count = reset_and_import()
        print(f"Selesai: {count} rekod diimport ke {DB_PATH}")
        sys.exit(0)
    init_db()
    host = os.environ.get("IKAWAL_HOST", "127.0.0.1")
    port = int(os.environ.get("IKAWAL_PORT", "5000"))
    debug = os.environ.get("IKAWAL_DEBUG", "1") == "1"
    print("=" * 68)
    print("  Iringkawal Analyzer + Supervisor Dashboard - BPK 2026")
    print(f"  Dashboard : http://{host}:{port}/")
    print(f"  app.html  : http://{host}:{port}/app   (wired to this backend)")
    print("  Demo: staff2026 / penyelia2026 / boss2026")
    print("=" * 68)
    app.run(host=host, port=port, debug=debug)
