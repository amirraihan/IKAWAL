# -*- coding: utf-8 -*-
"""
build_data.py  —  jana dashboard/data.js daripada dataset sebenar.

Guna:
    python dashboard/build_data.py

Input : data/iringkawal_bpk2026.xlsx   (15 kolum, 2,115 baris)
Output: dashboard/data.js

Nota: 'risk' (Kategori Risiko Kes Terbuka) tiada kolum sumber dalam Excel,
jadi ia kekal sebagai anggaran ilustratif. 'severity' dikira heuristik
daripada teks KESALAHAN. Semua carta lain dikira daripada data sebenar.
"""
import os, re, json
from collections import Counter, defaultdict
import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
XLSX = os.path.join(ROOT, "data", "iringkawal_bpk2026.xlsx")
OUT = os.path.join(HERE, "data.js")

NAVY = "#0B2C4A"; NAVY2 = "#163E63"; YELLOW = "#F2B705"
RED = "#E5484D"; ORANGE = "#F2762E"; GREEN = "#2E9E5B"; CYAN = "#35B6C9"

MONTHS = ["Jan", "Feb", "Mac", "Apr", "Mei", "Jun", "Jul", "Ogos", "Sep", "Okt", "Nov", "Dis"]


def norm(v):
    return re.sub(r"\s+", " ", str(v)).strip() if v is not None else ""


def upper(v):
    return norm(v).upper()


def parse_date(v):
    s = norm(v)
    m = re.match(r"^(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})", s)
    if m:
        return int(m.group(3)), int(m.group(2)), int(m.group(1))  # y,m,d
    return None


def days_between(a, b):
    if not a or not b:
        return None
    import datetime
    da = datetime.date(a[0], a[1], a[2]); db = datetime.date(b[0], b[1], b[2])
    return (db - da).days


def title(v):
    return norm(v).title()


def akta_of(kes):
    s = upper(kes)
    if "DADAH" in s or "1952" in s or "ADB" in s or "AKTA DADAH" in s:
        return "Dadah Berbahaya 1952"
    if "ARJT" in s:
        return "ARJT"
    if "PERTUBUHAN" in s or "PERSATUAN" in s:
        return "Pertubuhan"
    if ("KESEKSAAN" in s or "PENAL" in s or "KANUN" in s or "SENJATA" in s):
        return "Kanun Keseksaan"
    if ("IMIGRESEN" in s or "IMM" in s or "PASPORT" in s or "PASPOT" in s or "PLKS" in s
            or "IMMIGRATION" in s or s.startswith("SEK")):
        return "Imigresen"
    return "Lain-lain"


def severity_of(kes):
    s = upper(kes)
    if "DADAH" in s or "ARJT" in s or "SENJATA" in s:
        return "Sangat Serius"
    if "KESEKSAAN" in s or "PENAL" in s or "KANUN" in s:
        return "Serius"
    if "IMIGRESEN" in s or "IMM" in s or "PASPORT" in s or "PLKS" in s or s.startswith("SEK"):
        return "Sederhana"
    return "Ringan"


def age_group(u):
    if u is None:
        return None
    try:
        n = int(float(u))
    except Exception:
        return None
    if n < 30: return "18-29"
    if n < 45: return "30-44"
    if n < 60: return "45-59"
    return "60+"


def main():
    wb = openpyxl.load_workbook(XLSX, data_only=True, read_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    hdr = [upper(h) for h in rows[0]]

    def ci(*keys):
        for i, h in enumerate(hdr):
            for k in keys:
                if k in h:
                    return i
        return -1

    I_MASUK = ci("TARIKH MASUK"); I_TAMAT = ci("TARIKH TAMAT")
    I_NAMA = ci("NAMA"); I_JANT = ci("JANTINA"); I_UMUR = ci("UMUR")
    I_BANGSA = ci("BANGSA"); I_WARGA = ci("WARGANEGARA"); I_REMAN = ci("REMAN")
    I_PEG = ci("PEGAWAI"); I_DEPOT = ci("DEPOT"); I_TIND = ci("TINDAKAN"); I_KES = ci("KESALAHAN")

    data = []
    for r in rows[1:]:
        if not norm(r[I_NAMA]) and not norm(r[I_REMAN]):
            continue
        data.append(r)
    n = len(data)

    # ---------- aggregates ----------
    warga = Counter(); depot = Counter(); tind = Counter(); peg = Counter()
    bangsa_by_warga = defaultdict(Counter)
    age_pyr = {"18-29": [0, 0], "30-44": [0, 0], "45-59": [0, 0], "60+": [0, 0]}  # [male, female]
    age_bins = ["18-20", "21-23", "24-26", "27-29", "30-32", "33-35", "36-38", "39-41", "42-44", "45-47", "48+"]
    age_dist = Counter()
    akta_cnt = Counter(); sev = Counter()
    akta_age = defaultdict(lambda: Counter())     # akta -> age_group
    month_all = Counter(); month_over14 = Counter()
    days_all = []
    usir_by_month = defaultdict(lambda: [0, 0])   # month -> [usir, total]
    peg_missing = defaultdict(lambda: [0, 0])     # peg -> [missing_count, total]

    for r in data:
        w = upper(r[I_WARGA]) or "TIADA"; warga[w] += 1
        d = upper(r[I_DEPOT]); depot[d] += 1
        t = upper(r[I_TIND]) or "TIADA"; tind[t] += 1
        pg = upper(r[I_PEG]) or "TIADA"; peg[pg] += 1
        bangsa_by_warga[w][upper(r[I_BANGSA]) or "TIADA"] += 1

        j = upper(r[I_JANT]); g = age_group(r[I_UMUR])
        if g:
            age_pyr[g][0 if j == "LELAKI" else 1] += 1
            # bins
            try:
                un = int(float(r[I_UMUR]))
            except Exception:
                un = None
            if un is not None:
                for lbl in age_bins:
                    if lbl.endswith("+"):
                        lo = int(lbl[:-1])
                        if un >= lo: age_dist[lbl] += 1; break
                    else:
                        lo, hi = [int(x) for x in lbl.split("-")]
                        if lo <= un <= hi: age_dist[lbl] += 1; break

        a = akta_of(r[I_KES]); akta_cnt[a] += 1
        if g: akta_age[a][g] += 1
        sev[severity_of(r[I_KES])] += 1

        masuk = parse_date(r[I_MASUK]); tamat = parse_date(r[I_TAMAT])
        dur = days_between(masuk, tamat)
        if dur is not None:
            days_all.append(dur)
        if masuk:
            mi = masuk[1] - 1
            month_all[mi] += 1
            if dur is not None and dur > 14:
                month_over14[mi] += 1
            isusir = 1 if t == "USIR" else 0
            usir_by_month[mi][0] += isusir; usir_by_month[mi][1] += 1

        # data quality per pegawai: missing fields
        miss = 0
        if not upper(r[I_KES]): miss += 1
        if not norm(r[I_UMUR]): miss += 1
        if not norm(r[I_TAMAT]): miss += 1
        peg_missing[pg][0] += (1 if miss else 0); peg_missing[pg][1] += 1

    tanggal_masuk = [parse_date(r[I_MASUK]) for r in data]
    tanggal_masuk = [x for x in tanggal_masuk if x]
    y0, m0, d0 = min(tanggal_masuk); y1, m1, d1 = max(tanggal_masuk)
    ref_from = "%02d/%02d/%04d" % (d0, m0, y0)
    ref_to = "%02d/%02d/%04d" % (d1, m1, y1)

    total = n
    filipina = warga.get("FILIPINA", 0)
    fil_pct = round(filipina / total * 100)
    usir = tind.get("USIR", 0)
    base = sum(v for k, v in tind.items() if k not in ("TIADA",))
    usir_rate = round(usir / base * 100, 1) if base else 0
    over14 = sum(1 for x in days_all if x > 14)

    # delta kadar usir: bulan terakhir vs sebelumnya
    months_present = sorted(usir_by_month.keys())
    delta = 0.0
    if len(months_present) >= 2:
        a, b = months_present[-2], months_present[-1]
        ra = usir_by_month[a][0] / usir_by_month[a][1] * 100 if usir_by_month[a][1] else 0
        rb = usir_by_month[b][0] / usir_by_month[b][1] * 100 if usir_by_month[b][1] else 0
        delta = round(rb - ra, 1)
    delta_label = "dari " + MONTHS[months_present[-2]] if len(months_present) >= 2 else "bulan lalu"

    # nationality bars
    nat_pairs = sorted(((k, v) for k, v in warga.items() if k != "TIADA"), key=lambda x: -x[1])
    nat_bars = []
    for i, (k, v) in enumerate(nat_pairs):
        nat_bars.append({"name": title(k), "value": v, "color": YELLOW if i == 0 else NAVY})

    # treemap: warganegara -> bangsa
    treemap = []
    tree_colors = [NAVY, NAVY2, "#1E4E7A", "#2F5B8A"]
    for i, (k, v) in enumerate(nat_pairs[:4]):
        kids = bangsa_by_warga[k].most_common(6)
        if len(kids) < 1:
            continue
        treemap.append({
            "name": k, "size": v, "color": tree_colors[i % len(tree_colors)],
            "children": [{"name": b, "size": s} for b, s in kids],
        })

    # depot trend by month
    dim = max(month_all.keys()) + 1 if month_all else 0
    labels = MONTHS[:dim]
    dikk = [0] * dim; dip = [0] * dim
    for r in data:
        masuk = parse_date(r[I_MASUK])
        if not masuk:
            continue
        mi = masuk[1] - 1
        dp = upper(r[I_DEPOT])
        if "KOTA KINABALU" in dp:
            dikk[mi] += 1
        elif "PAPAR" in dp:
            dip[mi] += 1

    # bubbles: pegawai
    bubbles = []
    for pg, c in peg.most_common(8):
        if pg == "TIADA":
            continue
        mm, tt = peg_missing[pg]
        kual = round((1 - mm / tt) * 100) if tt else 0
        if kual >= 96: cat, col = "Tiada kes", GREEN
        elif kual >= 90: cat, col = "Sederhana", YELLOW
        elif kual >= 80: cat, col = "Tinggi", ORANGE
        else: cat, col = "Kritikal", RED
        bubbles.append({"name": pg, "x": c, "y": kual, "r": c, "cat": cat, "color": col})

    # akta x age heatmap (% within akta)
    akta_order = ["Imigresen", "Dadah Berbahaya 1952", "Kanun Keseksaan", "Lain-lain", "ARJT", "Pertubuhan"]
    fro = ["18-29", "30-44", "45-59", "60+"]
    akta_rows, akta_vals = [], []
    for a in akta_order:
        if akta_cnt.get(a, 0) == 0:
            continue
        tot = sum(akta_age[a].values()) or 1
        akta_rows.append(a)
        akta_vals.append([round(akta_age[a].get(g, 0) / tot * 100) for g in fro])

    # monthly reman baharu + lanjutan(>14)
    monthly = {"labels": labels, "baharu": [month_all.get(i, 0) for i in range(dim)],
               "lanjutan": [month_over14.get(i, 0) for i in range(dim)]}

    # origin map
    COORD = {
        "FILIPINA": (12.88, 121.77), "INDONESIA": (-2.50, 118.00), "CHINA": (35.00, 105.00),
        "VIETNAM": (14.06, 108.28), "PAKISTAN": (30.37, 69.35), "INDIA": (20.59, 78.96),
        "STATELESS": (3.14, 101.69), "TAIWAN": (23.70, 120.96), "THAILAND": (15.87, 100.99),
        "BANGLADESH": (23.68, 90.36), "MYANMAR": (21.91, 95.96),
    }
    origin = []
    for k, v in nat_pairs:
        if k in COORD:
            ak = "Imigresen"
            la, ln = COORD[k]
            origin.append({"name": title(k), "lat": la, "lng": ln, "count": v, "akta": ak,
                           "color": YELLOW if k == "FILIPINA" else (NAVY if v > 50 else "#6B7A90")})

    # severity (heuristik) & risk (anggaran ilustratif)
    sev_colors = {"Sangat Serius": RED, "Serius": ORANGE, "Sederhana": YELLOW, "Ringan": GREEN}
    severity = [{"name": k, "value": sev.get(k, 0), "color": sev_colors[k]}
                for k in ["Sangat Serius", "Serius", "Sederhana", "Ringan"]]

    def opt(seq):
        return ["Semua"] + seq

    obj = {
        "meta": {"title": "DASHBOARD REMAN JIM SABAH",
                 "subtitle": "Iringkawal \u00b7 Jabatan Imigresen Malaysia Sabah",
                 "refFrom": ref_from, "refTo": ref_to, "dummy": False},
        "options": {
            "depot": opt(["DIKK (Kota Kinabalu)", "DIP (Papar)"]),
            "warganegara": opt([title(k) for k, _ in nat_pairs]),
            "akta": opt(akta_rows),
            "keseriusan": opt(["Sangat Serius", "Serius", "Sederhana", "Ringan"]),
            "pegawai": opt([p for p, _ in peg.most_common() if p != "TIADA"]),
            "tindakan": opt(["Usir", "Bebas", "Usir/BLI"]),
        },
        "kpi": {
            "totalReman": total,
            "nationalityPie": [{"name": "Filipina", "value": fil_pct, "color": NAVY},
                               {"name": "Lain-lain", "value": 100 - fil_pct, "color": YELLOW}],
            "usirRate": usir_rate,
            "usirDelta": delta,
            "usirDeltaLabel": delta_label,
            "over14": over14,
            "risk": [{"name": "Paling Tinggi", "value": 7, "color": RED},
                     {"name": "Tinggi", "value": 1, "color": ORANGE},
                     {"name": "Sederhana", "value": 75, "color": YELLOW},
                     {"name": "Rendah", "value": 24, "color": GREEN}],
            "riskTotal": 107,
            "severity": severity,
        },
        "agePyramid": [{"group": g, "male": age_pyr[g][0], "female": age_pyr[g][1]}
                       for g in ["60+", "45-59", "30-44", "18-29"]],
        "ageDistribution": {"labels": age_bins, "values": [age_dist.get(l, 0) for l in age_bins]},
        "nationalityBars": nat_bars,
        "treemap": treemap,
        "depotTrend": {"labels": labels, "DIKK": dikk, "DIP": dip},
        "bubbles": bubbles,
        "aktaAge": {"rows": akta_rows, "cols": fro, "values": akta_vals},
        "monthlyReman": monthly,
        "originMap": origin,
        "jimSabah": {"lat": 5.98, "lng": 116.07, "name": "JIM SABAH (Kota Kinabalu)"},
    }

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("// data.js \u2014 dijana daripada data/iringkawal_bpk2026.xlsx oleh dashboard/build_data.py\n")
        f.write("// Jangan edit manual; jalankan semula:  python dashboard/build_data.py\n")
        f.write("const REMAN_DATA = ")
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write(";\n")

    print("Rows:", total, "| Filipina:", filipina, "| Usir rate:", usir_rate, "% | over14:", over14)
    print("wrote", OUT, os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    main()
