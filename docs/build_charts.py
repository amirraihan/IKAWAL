# -*- coding: utf-8 -*-
"""
build_charts.py — jana semua carta/graf dashboard (Reman JIM Sabah) sebagai PNG
untuk dimasukkan ke dalam TDD (PDF).

Sumber data: dashboard/data.js  (agregat sebenar)
Output     : docs/_charts/*.png

Guna:
    python docs/build_charts.py
"""
import os, re, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATAJS = os.path.join(ROOT, "dashboard", "data.js")
OUT = os.path.join(HERE, "_charts")
os.makedirs(OUT, exist_ok=True)

NAVY = "#0B2C4A"; NAVY2 = "#163E63"; YELLOW = "#F2B705"
RED = "#E5484D"; ORANGE = "#F2762E"; GREEN = "#2E9E5B"; CYAN = "#35B6C9"; GREY = "#6B7A90"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9,
    "axes.edgecolor": "#C7D3E0", "axes.labelcolor": "#33445A",
    "text.color": "#1C2B3A", "xtick.color": "#5F7389", "ytick.color": "#5F7389",
    "figure.facecolor": "white", "axes.facecolor": "white",
})

def parse_data():
    s = open(DATAJS, encoding="utf-8").read()
    m = re.search(r"const\s+REMAN_DATA\s*=\s*(\{.*\})\s*;", s, re.S)
    return json.loads(m.group(1))

def save(fig, name):
    path = os.path.join(OUT, name)
    fig.tight_layout()
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print("  ", name)

def clean(ax):
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.grid(axis="y", color="#EDF2F8", linewidth=0.8)
    ax.set_axisbelow(True)

D = parse_data()
kpi = D["kpi"]

# 1. Pecahan warganegara (donut)
fig, ax = plt.subplots(figsize=(4.6, 3.6))
pie = kpi["nationalityPie"]
ax.pie([p["value"] for p in pie], labels=[p["name"] for p in pie], colors=[p["color"] for p in pie],
       autopct="%1.0f%%", startangle=90, wedgeprops=dict(width=0.42, edgecolor="white"),
       textprops=dict(color=NAVY, fontsize=9))
ax.set_title("Jumlah Reman — Pecahan Warganegara", color=NAVY, fontweight="bold")
save(fig, "chart_01_pecahan_warganegara.png")

# 2. Kategori risiko kes terbuka
fig, ax = plt.subplots(figsize=(5.2, 3.2))
r = kpi["risk"]
ax.barh([x["name"] for x in r], [x["value"] for x in r], color=[x["color"] for x in r])
for i, x in enumerate(r):
    ax.text(x["value"] + 0.6, i, str(x["value"]), va="center", color=NAVY, fontweight="bold")
ax.invert_yaxis(); clean(ax); ax.grid(axis="x", color="#EDF2F8"); ax.grid(axis="y", visible=False)
ax.set_title("Kategori Risiko Kes Terbuka", color=NAVY, fontweight="bold")
save(fig, "chart_02_risiko_kes.png")

# 3. Keseriusan
fig, ax = plt.subplots(figsize=(5.2, 3.2))
sev = kpi["severity"]
ax.bar([x["name"] for x in sev], [x["value"] for x in sev], color=[x["color"] for x in sev])
for i, x in enumerate(sev):
    ax.text(i, x["value"] + max(sev, key=lambda z: z["value"])["value"] * 0.01, str(x["value"]), ha="center", color=NAVY, fontweight="bold")
clean(ax)
ax.set_title("Pecahan Keseriusan Kes", color=NAVY, fontweight="bold")
save(fig, "chart_03_keseriusan.png")

# 4. Piramid jantina x umur
fig, ax = plt.subplots(figsize=(5.6, 3.4))
pyr = D["agePyramid"]
groups = [g["group"] for g in pyr]
male = [-g["male"] for g in pyr]; female = [g["female"] for g in pyr]
y = np.arange(len(groups))
ax.barh(y, male, color=NAVY, label="Lelaki")
ax.barh(y, female, color=YELLOW, label="Perempuan")
for i, g in enumerate(pyr):
    ax.text(male[i] - 12, i, str(g["male"]), va="center", ha="right", color=NAVY, fontsize=8)
    ax.text(female[i] + 12, i, str(g["female"]), va="center", color=NAVY, fontsize=8)
ax.set_yticks(y); ax.set_yticklabels(groups)
ax.set_xticklabels([abs(int(t)) for t in ax.get_xticks()])
ax.axvline(0, color="#9FB0C4", lw=1)
clean(ax); ax.legend(frameon=False, loc="lower right")
ax.set_title("Piramid Jantina & Kumpulan Umur", color=NAVY, fontweight="bold")
save(fig, "chart_04_piramid_umur.png")

# 5. Taburan umur
fig, ax = plt.subplots(figsize=(6.4, 3.2))
ad = D["ageDistribution"]
ax.bar(ad["labels"], ad["values"], color=NAVY)
clean(ax)
plt.setp(ax.get_xticklabels(), rotation=35, ha="right")
ax.set_title("Taburan Umur Tahanan", color=NAVY, fontweight="bold")
save(fig, "chart_05_taburan_umur.png")

# 6. Pecahan warganegara (bar)
fig, ax = plt.subplots(figsize=(5.8, 3.6))
nb = D["nationalityBars"]
ax.barh([x["name"] for x in nb], [x["value"] for x in nb], color=[x["color"] for x in nb])
for i, x in enumerate(nb):
    ax.text(x["value"] + max(nb, key=lambda z: z["value"])["value"] * 0.01, i, str(x["value"]), va="center", color=NAVY, fontsize=8)
ax.invert_yaxis(); clean(ax); ax.grid(axis="x", color="#EDF2F8"); ax.grid(axis="y", visible=False)
ax.set_title("Pecahan Warganegara", color=NAVY, fontweight="bold")
save(fig, "chart_06_pecahan_warganegara_bar.png")

# 7. Treemap warganegara -> bangsa (slice-and-dice)
fig, ax = plt.subplots(figsize=(6.4, 3.6))
tree = D["treemap"]
total = sum(t["size"] for t in tree)
x0 = 0.0
for t in tree:
    w = t["size"] / total
    y0 = 0.0; ctot = sum(c["size"] for c in t["children"]) or 1
    for c in t["children"]:
        h = c["size"] / ctot
        ax.add_patch(Rectangle((x0, y0), w, h, facecolor=t["color"], edgecolor="white", lw=2, alpha=0.85 + 0.15 * (c["size"] / ctot)))
        ax.text(x0 + w / 2, y0 + h / 2, "%s\n%s" % (c["name"], f'{c["size"]:,}'), ha="center", va="center", color="white", fontsize=8.5, fontweight="bold")
        y0 += h
    ax.text(x0 + w / 2, 1.02, "%s" % t["name"], ha="center", va="bottom", color=NAVY, fontweight="bold")
    x0 += w
ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
ax.set_title("Warganegara -> Bangsa (saiz = bilangan kes)", color=NAVY, fontweight="bold")
save(fig, "chart_07_treemap_bangsa.png")

# 8. Trend reman mengikut depot
fig, ax = plt.subplots(figsize=(6.4, 3.2))
dt = D["depotTrend"]
ax.plot(dt["labels"], dt["DIKK"], "-o", color=NAVY, lw=2, ms=4, label="DIKK (Kota Kinabalu)")
ax.plot(dt["labels"], dt["DIP"], "-o", color=YELLOW, lw=2, ms=4, label="DIP (Papar)")
clean(ax); ax.legend(frameon=False)
ax.set_title("Trend Reman Mengikut Depot", color=NAVY, fontweight="bold")
save(fig, "chart_08_trend_depot.png")

# 9. Bubble beban kes vs kualiti data
fig, ax = plt.subplots(figsize=(6.0, 3.6))
bub = D["bubbles"]
for b in bub:
    ax.scatter(b["x"], b["y"], s=b["r"] * 8, color=b["color"], alpha=0.8, edgecolor="white")
    ax.annotate(b["name"], (b["x"], b["y"]), fontsize=7.5, color=NAVY2, xytext=(0, 10), textcoords="offset points", ha="center")
seen = {}
for b in bub:
    seen[b["cat"]] = b["color"]
for cat, col in [("Kritikal", RED), ("Tinggi", ORANGE), ("Sederhana", YELLOW), ("Tiada kes", GREEN)]:
    ax.scatter([], [], color=col, label=cat)
ax.set_xlabel("Beban kes"); ax.set_ylabel("Skor kualiti data")
ax.grid(color="#EDF2F8"); ax.set_axisbelow(True)
for sp in ("top", "right"):
    ax.spines[sp].set_visible(False)
ax.legend(frameon=False, fontsize=8)
ax.set_title("Korelasi Beban Kes & Kualiti Data (pegawai)", color=NAVY, fontweight="bold")
save(fig, "chart_09_bubble_pegawai.png")

# 10. Heatmap akta x kumpulan umur
fig, ax = plt.subplots(figsize=(6.0, 3.4))
aa = D["aktaAge"]
vals = np.array(aa["values"])
im = ax.imshow(vals, cmap="Blues", aspect="auto")
ax.set_xticks(range(len(aa["cols"]))); ax.set_xticklabels(aa["cols"])
ax.set_yticks(range(len(aa["rows"]))); ax.set_yticklabels(aa["rows"])
for i in range(vals.shape[0]):
    for j in range(vals.shape[1]):
        ax.text(j, i, "%d%%" % vals[i, j], ha="center", va="center",
                color="white" if vals[i, j] > vals.max() * 0.6 else NAVY, fontweight="bold", fontsize=8.5)
ax.set_title("Akta x Kumpulan Umur (% dalam setiap akta)", color=NAVY, fontweight="bold")
save(fig, "chart_10_heatmap_akta_umur.png")

# 11. Trend reman baharu + >14 hari (stacked)
fig, ax = plt.subplots(figsize=(6.4, 3.2))
mr = D["monthlyReman"]
ax.bar(mr["labels"], mr["baharu"], color=NAVY, label="Reman baharu")
ax.bar(mr["labels"], mr["lanjutan"], bottom=mr["baharu"], color=CYAN, label="Reman >14 hari")
clean(ax); ax.legend(frameon=False)
ax.set_title("Trend Reman Baharu & Lanjutan (>14 hari) Mengikut Bulan", color=NAVY, fontweight="bold")
save(fig, "chart_11_trend_bulanan.png")

print("Siap. Carta dalam:", OUT)
