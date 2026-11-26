"""Phase 1: Monthly KPI Snapshot, Rule-Based Insights & Privacy Guard (UC-4 / E9)."""

from __future__ import annotations

import datetime as dt
import os
import re
import sqlite3
from collections import Counter
from typing import Any

from uc4.contracts import SCHEMA_VERSION, assert_kpi_payload_safe

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DB_PATH = os.environ.get("IKAWAL_DB", os.path.join(BASE_DIR, "ikawal.db"))

BLN_MS = [
    "Januari", "Februari", "Mac", "April", "Mei", "Jun",
    "Julai", "Ogos", "September", "Oktober", "November", "Disember",
]

ACT_GROUPS = (
    "Akta Imigresen 1959/63",
    "Akta Dadah Berbahaya 1952",
    "Kanun Keseksaan",
    "Akta Kastam 1967",
    "Lain-lain / Tidak Jelas",
)


def parse_iso_date(value: Any) -> dt.date | None:
    """Parse an ISO YYYY-MM-DD date string safely."""
    if not value:
        return None
    s = str(value).strip()[:10]
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        return None


def month_label_ms(month_ym: str) -> str:
    """Convert '2026-10' into 'Oktober 2026'."""
    try:
        year_s, mon_s = month_ym.split("-")
        mon_idx = int(mon_s)
        if 1 <= mon_idx <= 12:
            return f"{BLN_MS[mon_idx - 1]} {year_s}"
    except (ValueError, IndexError):
        pass
    return month_ym


def prev_month_ym(month_ym: str) -> str:
    """Return the preceding calendar month in YYYY-MM format."""
    year, mon = (int(x) for x in month_ym.split("-"))
    if mon == 1:
        return f"{year - 1:04d}-12"
    return f"{year:04d}-{mon - 1:02d}"


def record_month(rec: dict[str, Any]) -> str:
    """Determine cohort month (YYYY-MM) using tarikh_masuk first, then tarikh_tamat_reman."""
    for field in ("tarikh_masuk", "tarikh_tamat_reman"):
        d = parse_iso_date(rec.get(field))
        if d is not None:
            return f"{d.year:04d}-{d.month:02d}"
    return ""


def classify_act(raw_offence: Any) -> str:
    """Map raw KESALAHAN text into standard Malaysian statute groups."""
    txt = str(raw_offence or "").upper().strip()
    if not txt or txt in ("-", "NIL", "TIADA"):
        return "Lain-lain / Tidak Jelas"
    if any(tok in txt for tok in ("ADB", "DADAH", "15(1)(A)", "39A", "39B", "12(2)", "12(3)")):
        return "Akta Dadah Berbahaya 1952"
    if any(tok in txt for tok in ("IMMG", "IMIGRESEN", "IMM", "6(1)", "5(2)", "15(1)©", "15(1)(C)", "55B", "56(")):
        return "Akta Imigresen 1959/63"
    if any(tok in txt for tok in ("KK", "KANUN", "PENAL", "411", "414", "506", "323", "379", "380", "420")):
        return "Kanun Keseksaan"
    if "KASTAM" in txt or "CUSTOM" in txt:
        return "Akta Kastam 1967"
    return "Lain-lain / Tidak Jelas"


def normalize_section(raw_offence: Any) -> str:
    """Normalize messy section spellings (e.g. '6(1)( C ) Immg' -> '6(1)(C) IMMG')."""
    txt = str(raw_offence or "").strip()
    if not txt:
        return "Tidak dinyatakan"
    txt = txt.replace("\u00a9", "(C)").replace("©", "(C)")
    txt = re.sub(r"\s+", " ", txt).upper()
    txt = re.sub(r"\(\s+([A-Z0-9]+)\s+\)", r"(\1)", txt)
    txt = re.sub(r"\(\s+([A-Z0-9]+)\)", r"(\1)", txt)
    txt = re.sub(r"\(([A-Z0-9]+)\s+\)", r"(\1)", txt)
    return txt


def age_band(umur: Any) -> str:
    """Bucket integer age into UC-1/UC-4 demographic bands."""
    try:
        age = int(umur)
    except (TypeError, ValueError):
        return "Tidak diketahui"
    if age < 18:
        return "<18"
    if age <= 29:
        return "18-29"
    if age <= 44:
        return "30-44"
    if age <= 59:
        return "45-59"
    return "60+"


def is_bebas(rec: dict[str, Any]) -> bool:
    return bool((rec.get("tarikh_dibebaskan") or "").strip()) or (rec.get("tindakan") or "").strip().lower() == "bebas"


def is_urgent(rec: dict[str, Any], ref_date: dt.date) -> bool:
    if is_bebas(rec):
        return False
    end = parse_iso_date(rec.get("tarikh_tamat_reman"))
    if end is None:
        return False
    return (end - ref_date).days <= 3


def reman_duration_days(rec: dict[str, Any]) -> int | None:
    start = parse_iso_date(rec.get("tarikh_masuk"))
    end = parse_iso_date(rec.get("tarikh_tamat_reman"))
    if start is None or end is None:
        return None
    return (end - start).days + 1


def load_records_from_sqlite(db_path: str | None = None) -> list[dict[str, Any]]:
    """Read all records from SQLite in read-only mode when available."""
    path = db_path or DEFAULT_DB_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(f"Database not found: {path}")

    uri = f"file:{os.path.abspath(path)}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.OperationalError:
        conn = sqlite3.connect(path)

    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM records ORDER BY created_at").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def available_months(records: list[dict[str, Any]]) -> list[str]:
    """Return sorted list of valid cohort months (YYYY-MM) found in records."""
    months = {record_month(r) for r in records}
    months.discard("")
    return sorted(months)


def _top_counts(counter: Counter[str], total: int, limit: int = 10) -> list[dict[str, Any]]:
    out = []
    for name, count in counter.most_common(limit):
        pct = round(count / total * 100, 1) if total else 0.0
        out.append({"name": name, "count": count, "pct": pct})
    return out


def _aggregate_subset(subset: list[dict[str, Any]], ref_date: dt.date) -> dict[str, Any]:
    total = len(subset)
    bebas_count = sum(1 for r in subset if is_bebas(r))
    aktif_count = total - bebas_count
    urgent_count = sum(1 for r in subset if is_urgent(r, ref_date))
    extended_count = sum(
        1 for r in subset
        if (dur := reman_duration_days(r)) is not None and 14 < dur <= 90
    )

    jantina_c: Counter[str] = Counter()
    depot_c: Counter[str] = Counter()
    warga_c: Counter[str] = Counter()
    bangsa_c: Counter[str] = Counter()
    akta_c: Counter[str] = Counter()
    seksyen_c: Counter[str] = Counter()
    tindakan_c: Counter[str] = Counter()
    pegawai_c: Counter[str] = Counter()
    umur_c: Counter[str] = Counter()

    blank_reman = 0
    end_before_start = 0
    anomalous_year = 0

    for r in subset:
        jantina_c[(r.get("jantina") or "Tidak dinyatakan").strip() or "Tidak dinyatakan"] += 1
        depot_c[(r.get("depot") or "Tidak dinyatakan").strip() or "Tidak dinyatakan"] += 1
        warga_c[(r.get("warganegara") or "Tidak dinyatakan").strip() or "Tidak dinyatakan"] += 1
        bangsa_c[(r.get("bangsa") or "Tidak dinyatakan").strip() or "Tidak dinyatakan"] += 1
        akta_c[classify_act(r.get("jenis_kesalahan"))] += 1
        seksyen_c[normalize_section(r.get("jenis_kesalahan"))] += 1
        tindakan_c[(r.get("tindakan") or "Tiada").strip() or "Tiada"] += 1
        pegawai_c[(r.get("pegawai") or "(Tiada Pegawai)").strip() or "(Tiada Pegawai)"] += 1
        umur_c[age_band(r.get("umur"))] += 1

        if not (r.get("nombor_reman") or "").strip():
            blank_reman += 1
        start = parse_iso_date(r.get("tarikh_masuk"))
        end = parse_iso_date(r.get("tarikh_tamat_reman"))
        if start and end and end < start:
            end_before_start += 1
        if end and end.year > ref_date.year + 2:
            anomalous_year += 1

    officer_count = len([k for k in pegawai_c if k != "(Tiada Pegawai)"])
    avg_officer = round(total / officer_count, 1) if officer_count else 0.0
    top_off_name, top_off_count = pegawai_c.most_common(1)[0] if pegawai_c else ("-", 0)

    return {
        "total_reman": total,
        "aktif": aktif_count,
        "bebas": bebas_count,
        "urgent_atau_tertunggak": urgent_count,
        "tempoh_lebih_14_hari": extended_count,
        "jantina": _top_counts(jantina_c, total, limit=10),
        "depot": _top_counts(depot_c, total, limit=10),
        "warganegara": _top_counts(warga_c, total, limit=15),
        "bangsa": _top_counts(bangsa_c, total, limit=15),
        "akta": _top_counts(akta_c, total, limit=10),
        "top_seksyen": _top_counts(seksyen_c, total, limit=10),
        "tindakan": _top_counts(tindakan_c, total, limit=10),
        "kumpulan_umur": _top_counts(umur_c, total, limit=10),
        "pegawai": {
            "jumlah_pegawai_aktif": officer_count,
            "purata_kes_per_pegawai": avg_officer,
            "beban_tertinggi": {"name": top_off_name, "count": top_off_count},
            "senarai": _top_counts(pegawai_c, total, limit=15),
        },
        "kualiti_data": {
            "nombor_reman_kosong": blank_reman,
            "tarikh_tamat_sebelum_masuk": end_before_start,
            "tahun_tamat_janggal": anomalous_year,
        },
    }


def _pct_delta(curr: int, prev: int) -> float | None:
    if prev == 0:
        return None
    return round((curr - prev) / prev * 100, 1)


def _counter_map(items: list[dict[str, Any]]) -> dict[str, int]:
    return {item["name"]: item["count"] for item in items}


def _compute_mom(curr_kpis: dict[str, Any], prev_kpis: dict[str, Any], prev_ym: str) -> dict[str, Any]:
    curr_total = curr_kpis["total_reman"]
    prev_total = prev_kpis["total_reman"]

    curr_depots = _counter_map(curr_kpis["depot"])
    prev_depots = _counter_map(prev_kpis["depot"])
    depot_deltas = []
    for dep in sorted(set(curr_depots) | set(prev_depots)):
        c_val = curr_depots.get(dep, 0)
        p_val = prev_depots.get(dep, 0)
        depot_deltas.append({
            "name": dep,
            "current": c_val,
            "previous": p_val,
            "delta": c_val - p_val,
            "pct_change": _pct_delta(c_val, p_val),
        })

    curr_acts = _counter_map(curr_kpis["akta"])
    prev_acts = _counter_map(prev_kpis["akta"])
    akta_deltas = []
    for act in sorted(set(curr_acts) | set(prev_acts)):
        c_val = curr_acts.get(act, 0)
        p_val = prev_acts.get(act, 0)
        akta_deltas.append({
            "name": act,
            "current": c_val,
            "previous": p_val,
            "delta": c_val - p_val,
            "pct_change": _pct_delta(c_val, p_val),
        })

    return {
        "prev_month": prev_ym,
        "prev_month_label": month_label_ms(prev_ym),
        "prev_total_reman": prev_total,
        "total_delta": curr_total - prev_total,
        "total_pct_change": _pct_delta(curr_total, prev_total),
        "urgent_delta": curr_kpis["urgent_atau_tertunggak"] - prev_kpis["urgent_atau_tertunggak"],
        "depots": depot_deltas,
        "akta": akta_deltas,
    }


def _build_infographics(subset: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute cross-tabulations needed by UC-4 infographics (current & Wave 4)."""
    warga_counts: Counter[str] = Counter()
    cross: dict[str, Counter[str]] = {}
    for r in subset:
        nat = (r.get("warganegara") or "Tidak dinyatakan").strip() or "Tidak dinyatakan"
        act = classify_act(r.get("jenis_kesalahan"))
        warga_counts[nat] += 1
        cross.setdefault(nat, Counter())[act] += 1

    top_nats = [name for name, _ in warga_counts.most_common(6)]
    if len(warga_counts) > 6:
        others_counter: Counter[str] = Counter()
        for nat, cnts in cross.items():
            if nat not in top_nats:
                others_counter.update(cnts)
        matrix_nats = top_nats + ["Lain-lain"]
        cross_with_others = {nat: cross[nat] for nat in top_nats}
        cross_with_others["Lain-lain"] = others_counter
    else:
        matrix_nats = top_nats
        cross_with_others = {nat: cross[nat] for nat in top_nats}

    rows = []
    for nat in matrix_nats:
        cnts = cross_with_others[nat]
        by_act = {act: cnts.get(act, 0) for act in ACT_GROUPS}
        rows.append({
            "warganegara": nat,
            "jumlah": sum(by_act.values()),
            "mengikut_akta": by_act,
        })

    sebab_list = Counter(
        (r.get("sebab_lebih_14_hari") or "").strip()
        for r in subset
        if (r.get("sebab_lebih_14_hari") or "").strip()
    )
    return {
        "pecahan_warganegara": _top_counts(warga_counts, len(subset), limit=10),
        "kesalahan_setiap_warganegara": {
            "akta_groups": list(ACT_GROUPS),
            "rows": rows,
        },
        "sebab_lebih_14_hari": {
            "field_available": bool(sebab_list),
            "nota": (
                "Data sebab lebih 14 hari tersedia."
                if sebab_list
                else "Menunggu medan baharu SEBAB LEBIH 14 HARI (Wave 4); paparan semasa guna kiraan tempoh > 14 hari."
            ),
            "pecahan": _top_counts(sebab_list, sum(sebab_list.values()), limit=10),
        },
    }


def _build_uc2_adapter(
    subset: list[dict[str, Any]],
    kpis: dict[str, Any],
    uc2_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    """Use real UC-2 output if supplied; otherwise compute safe baseline from UC-1 columns."""
    if uc2_summary:
        return {"integrated": True, "source": "uc2_module", **uc2_summary}
    return {
        "integrated": False,
        "source": "fallback_uc1_columns",
        "nota": "Modul UC-2 belum disepadukan; kiraan asas guna tarikh tamat & tempoh reman.",
        "kes_mendesak_atau_tertunggak": kpis["urgent_atau_tertunggak"],
        "kes_reman_lebih_14_hari": kpis["tempoh_lebih_14_hari"],
        "kes_rayuan_aktif": sum(
            1 for r in subset if r.get("surat_rayuan") in ("Diterima", "Dalam Semakan")
        ),
    }


def _build_uc3_adapter(
    all_records: list[dict[str, Any]],
    target_ym: str,
    uc3_forecast: dict[str, Any] | None,
) -> dict[str, Any]:
    """Use real UC-3 forecast if supplied; otherwise compute 3-month trailing depot average."""
    if uc3_forecast:
        return {"integrated": True, "source": "uc3_module", **uc3_forecast}

    m1 = prev_month_ym(target_ym)
    m2 = prev_month_ym(m1)
    window_months = [m2, m1, target_ym]
    depot_monthly: dict[str, list[int]] = {}
    for ym in window_months:
        sub = [r for r in all_records if record_month(r) == ym]
        counts = Counter((r.get("depot") or "Tidak dinyatakan").strip() or "Tidak dinyatakan" for r in sub)
        for dep in ("Kota Kinabalu", "Papar"):
            depot_monthly.setdefault(dep, []).append(counts.get(dep, 0))

    baseline = {
        dep: round(sum(vals) / len(vals), 1) if vals else 0.0
        for dep, vals in depot_monthly.items()
    }
    return {
        "integrated": False,
        "source": "fallback_3m_moving_avg",
        "nota": "Modul UC-3 belum disepadukan; anggaran asas guna purata 3 bulan terkini.",
        "tingkap_bulan": window_months,
        "anggaran_kemasukan_bulanan_depot": baseline,
    }


def generate_rule_insights(
    month_ym: str,
    kpis: dict[str, Any],
    mom: dict[str, Any],
) -> list[dict[str, Any]]:
    """Deterministic E9 insight rules derived strictly from computed KPI numbers."""
    insights: list[dict[str, Any]] = []
    total = kpis["total_reman"]
    if total == 0:
        return [{
            "code": "NO_DATA",
            "severity": "info",
            "title": "Tiada rekod bagi bulan dipilih",
            "detail": f"Tiada kemasukan atau tarikh reman direkodkan untuk {month_label_ms(month_ym)}.",
            "metric_value": 0,
        }]

    # 1. MoM intake change
    pct = mom.get("total_pct_change")
    delta = mom.get("total_delta", 0)
    if pct is not None:
        if pct >= 15.0:
            insights.append({
                "code": "MOM_SURGE",
                "severity": "tinggi",
                "title": "Lonjakan kemasukan reman bulanan",
                "detail": (
                    f"Jumlah kes meningkat {pct}% (+{delta} kes) berbanding "
                    f"{mom['prev_month_label']} ({mom['prev_total_reman']} -> {total})."
                ),
                "metric_value": pct,
            })
        elif pct <= -15.0:
            insights.append({
                "code": "MOM_DROP",
                "severity": "info",
                "title": "Penurunan ketara kemasukan reman",
                "detail": (
                    f"Jumlah kes menurun {abs(pct)}% ({delta} kes) berbanding "
                    f"{mom['prev_month_label']} ({mom['prev_total_reman']} -> {total})."
                ),
                "metric_value": pct,
            })

    # 2. Depot MoM divergence
    for d in mom.get("depots", []):
        dpct = d.get("pct_change")
        if dpct is not None and dpct >= 20.0 and d["current"] >= 10:
            insights.append({
                "code": "DEPOT_SURGE",
                "severity": "tinggi",
                "title": f"Tekanan kemasukan di Depot {d['name']}",
                "detail": (
                    f"Depot {d['name']} mencatat kenaikan {dpct}% (+{d['delta']} kes: "
                    f"{d['previous']} -> {d['current']})."
                ),
                "metric_value": d["current"],
            })

    # 3. Dominant offence act & nationality
    if kpis["akta"]:
        top_act = kpis["akta"][0]
        insights.append({
            "code": "TOP_ACT",
            "severity": "sederhana",
            "title": f"Kategori kesalahan tertinggi: {top_act['name']}",
            "detail": f"Menyumbang {top_act['count']} daripada {total} kes ({top_act['pct']}%).",
            "metric_value": top_act["pct"],
        })

    if kpis["warganegara"]:
        top_nat = kpis["warganegara"][0]
        insights.append({
            "code": "TOP_NATIONALITY",
            "severity": "info",
            "title": f"Warganegara dominan: {top_nat['name']}",
            "detail": f"{top_nat['count']} kes ({top_nat['pct']}%) daripada keseluruhan reman bulan ini.",
            "metric_value": top_nat["pct"],
        })

    # 4. Urgent / overdue cases
    urgent = kpis["urgent_atau_tertunggak"]
    if urgent > 0:
        urgent_pct = round(urgent / total * 100, 1)
        insights.append({
            "code": "URGENT_EXPOSURE",
            "severity": "kritikal" if urgent_pct >= 25.0 else "tinggi",
            "title": "Kes tamat reman <= 3 hari / tertunggak",
            "detail": f"{urgent} kes aktif ({urgent_pct}% daripada kohort bulan) memerlukan tindakan segera.",
            "metric_value": urgent,
        })

    # 5. Officer workload imbalance
    peg = kpis["pegawai"]
    avg_off = peg.get("purata_kes_per_pegawai", 0)
    top_off = peg.get("beban_tertinggi", {})
    if avg_off > 0 and top_off.get("count", 0) >= avg_off * 1.8 and top_off.get("count", 0) >= 10:
        insights.append({
            "code": "WORKLOAD_SKEW",
            "severity": "sederhana",
            "title": f"Beban kerja tidak sekata ({top_off['name']})",
            "detail": (
                f"{top_off['name']} mengendalikan {top_off['count']} kes berbanding "
                f"purata {avg_off} kes setiap pegawai."
            ),
            "metric_value": top_off["count"],
        })

    # 6. Data quality warnings
    dq = kpis["kualiti_data"]
    dq_issues = (
        dq["nombor_reman_kosong"]
        + dq["tarikh_tamat_sebelum_masuk"]
        + dq["tahun_tamat_janggal"]
    )
    if dq_issues > 0:
        insights.append({
            "code": "DATA_QUALITY",
            "severity": "sederhana",
            "title": "Isu kualiti data dikesan dalam kohort bulan ini",
            "detail": (
                f"No. Reman kosong: {dq['nombor_reman_kosong']}, "
                f"tamat sebelum masuk: {dq['tarikh_tamat_sebelum_masuk']}, "
                f"tahun tamat janggal: {dq['tahun_tamat_janggal']}."
            ),
            "metric_value": dq_issues,
        })

    return insights


def build_monthly_kpi(
    records: list[dict[str, Any]],
    month_ym: str | None = None,
    ref_date: dt.date | None = None,
    uc2_summary: dict[str, Any] | None = None,
    uc3_forecast: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a privacy-safe UC-4 monthly KPI + insight payload from records."""
    ref = ref_date or dt.date.today()
    months = available_months(records)
    if month_ym:
        target_ym = month_ym
    elif months:
        target_ym = months[-1]
    else:
        target_ym = f"{ref.year:04d}-{ref.month:02d}"

    prev_ym = prev_month_ym(target_ym)
    curr_records = [r for r in records if record_month(r) == target_ym]
    prev_records = [r for r in records if record_month(r) == prev_ym]

    curr_kpis = _aggregate_subset(curr_records, ref)
    prev_kpis = _aggregate_subset(prev_records, ref)
    mom = _compute_mom(curr_kpis, prev_kpis, prev_ym)
    insights = generate_rule_insights(target_ym, curr_kpis, mom)

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "phase": "phase1_kpi",
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "reference_date": ref.isoformat(),
        "month": target_ym,
        "month_label": month_label_ms(target_ym),
        "available_months": months,
        "privacy_guard": {
            "pii_stripped": True,
            "excluded_fields": ["nama", "catatan", "nombor_reman", "nombor_fail"],
        },
        "kpis": curr_kpis,
        "mom": mom,
        "infographics": _build_infographics(curr_records),
        "uc2_summary": _build_uc2_adapter(curr_records, curr_kpis, uc2_summary),
        "uc3_forecast": _build_uc3_adapter(records, target_ym, uc3_forecast),
        "insights": insights,
    }
    assert_kpi_payload_safe(payload)
    return payload
