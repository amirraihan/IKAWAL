"""UC-1 Interactive Monitoring Dashboard (Streamlit) + entry, worklist, forecast.

Run:  streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from smartdepot.audit import can_reveal_pii  # noqa: E402
from smartdepot.config import get_settings  # noqa: E402
from smartdepot.constants import (  # noqa: E402
    BANGSA_MAP, DEPOTS, KNOWN_BANGSA, KNOWN_NATIONALITIES, TINDAKAN_CODES,
)
from smartdepot.engines import decision_support, reman_engine  # noqa: E402
from smartdepot.ingest.loader import ingest_dataframe, ingest_form  # noqa: E402
from smartdepot.masking import mask_name, mask_record  # noqa: E402
from smartdepot.models import RemanForm  # noqa: E402
from smartdepot.pipeline import run_daily  # noqa: E402
from smartdepot.reporting import kpis, report_generator  # noqa: E402
from smartdepot.repository import RepanRepository  # noqa: E402

st.set_page_config(page_title="SmartDepot", page_icon="🏛️", layout="wide")


@st.cache_resource
def get_repo() -> RepanRepository:
    return RepanRepository(get_settings().db_path)


@st.cache_data(ttl=30, show_spinner=False)
def load_df() -> pd.DataFrame:
    return get_repo().to_dataframe()


def clear_caches() -> None:
    load_df.clear()


def money(n: float) -> str:
    return f"{n:,.0f}"


repo = get_repo()
settings = get_settings()

# ---------------------------------------------------------------------------
# Sidebar: role + global filters (design 5.1)
# ---------------------------------------------------------------------------
st.sidebar.title("SmartDepot")
role = st.sidebar.selectbox("Peranan (role)", ["officer", "depot_head", "hq"], index=2)
reveal = can_reveal_pii(role)
st.sidebar.caption("Semua output AI adalah **nasihat**; pegawai membuat keputusan.")

df_all = load_df()
if df_all.empty:
    st.warning("Tiada data. Jalankan `python scripts/seed_demo_data.py` dahulu.")
    st.stop()

st.sidebar.header("Penapis")
depot_opts = ["Semua"] + sorted(df_all["depot"].dropna().unique().tolist())
depot_sel = st.sidebar.selectbox("DEPOT", depot_opts)
warga_opts = ["Semua"] + sorted(df_all["warganegara"].dropna().unique().tolist())
warga_sel = st.sidebar.selectbox("WARGANEGARA", warga_opts)
akta_opts = ["Semua"] + sorted(df_all["akta"].dropna().unique().tolist())
akta_sel = st.sidebar.selectbox("Kumpulan Akta", akta_opts)
peg_opts = ["Semua"] + sorted(o for o in df_all["nama_pegawai"].dropna().unique() if o)
peg_sel = st.sidebar.selectbox("NAMA PEGAWAI", peg_opts)


def filtered(df: pd.DataFrame) -> pd.DataFrame:
    out = df
    if depot_sel != "Semua":
        out = out[out["depot"] == depot_sel]
    if warga_sel != "Semua":
        out = out[out["warganegara"] == warga_sel]
    if akta_sel != "Semua":
        out = out[out["akta"] == akta_sel]
    if peg_sel != "Semua":
        out = out[out["nama_pegawai"] == peg_sel]
    return out


df = filtered(df_all)

PAGES = [
    "Ringkasan", "Reman Tracker", "Profil Banduan", "Kesalahan",
    "Tindakan & Pegawai", "Kualiti Data",
    "Data Entry", "Priority Worklist", "Forecast", "Reports & Audit",
]
page = st.sidebar.radio("Halaman", PAGES)


# ---------------------------------------------------------------------------
# Page 1 — Ringkasan
# ---------------------------------------------------------------------------
if page == "Ringkasan":
    st.title("Ringkasan Operasi Reman")
    ov = kpis.overview_kpis(df)
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Jumlah reman", money(ov["jumlah_reman"]))
    c2.metric("Reman aktif", money(ov["reman_aktif"]))
    c3.metric("Tamat ≤ 3 hari", money(ov["tamat_3_hari"]))
    c4.metric("Tertunggak", money(ov["tertunggak"]))
    c5.metric("% Usir", f"{ov['pct_usir']}%")
    c6.metric("% Bebas", f"{ov['pct_bebas']}%")

    trend = kpis.monthly_summary(df)
    if not trend.empty:
        fig = px.bar(trend, x="bulan", y="bilangan", title="Reman baharu mengikut bulan")
        st.plotly_chart(fig, width="stretch")

    st.subheader("Status reman")
    sc = kpis.status_counts(df)
    if not sc.empty:
        st.plotly_chart(px.pie(sc, names="status_reman", values="bilangan", hole=0.45),
                        width="stretch")


# ---------------------------------------------------------------------------
# Page 2 — Reman Tracker
# ---------------------------------------------------------------------------
elif page == "Reman Tracker":
    st.title("Reman Tracker")
    st.caption("Disusun mengikut baki hari; berwarna mengikut label risiko UC-2.")
    view = df.sort_values("hari_berbaki", na_position="last").copy()
    view["nama_display"] = view["nama"] if reveal else view["nama"].map(mask_name)
    cols = ["no_reman", "nama_display", "depot", "warganegara", "hari_berbaki",
            "status_reman", "risk_score", "risk_label", "recommended_action"]
    st.dataframe(view[cols].head(500), width="stretch", height=560)
    st.download_button(
        "Muat turun senarai kes (XLSX)",
        data=report_generator.export_case_list(df, settings.output_dir / "senarai_kes.xlsx",
                                               reveal_pii=reveal).read_bytes(),
        file_name="senarai_kes.xlsx",
    )


# ---------------------------------------------------------------------------
# Page 3 — Profil Banduan
# ---------------------------------------------------------------------------
elif page == "Profil Banduan":
    st.title("Profil Banduan")
    bd = kpis.breakdowns(df)
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(px.bar(bd["warganegara"], x="bilangan", y="warganegara",
                               orientation="h", title="Pecahan warganegara"),
                        width="stretch")
        st.plotly_chart(px.bar(bd["bangsa"], x="bilangan", y="bangsa", orientation="h",
                               title="Bangsa"), width="stretch")
    with c2:
        st.plotly_chart(px.bar(bd["jantina"], x="jantina", y="bilangan", title="Jantina"),
                        width="stretch")
        st.plotly_chart(px.bar(bd["kumpulan_umur"], x="kumpulan_umur", y="bilangan",
                               title="Kumpulan umur"), width="stretch")


# ---------------------------------------------------------------------------
# Page 4 — Kesalahan
# ---------------------------------------------------------------------------
elif page == "Kesalahan":
    st.title("Kesalahan")
    bd = kpis.breakdowns(df)
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(px.pie(bd["akta"], names="akta", values="bilangan",
                               title="Kumpulan Akta"), width="stretch")
    with c2:
        st.plotly_chart(px.bar(bd["seksyen"], x="bilangan", y="seksyen",
                               orientation="h", title="Top 10 seksyen"),
                        width="stretch")
    cross = pd.crosstab(df["warganegara"], df["akta"])
    if not cross.empty:
        st.plotly_chart(px.imshow(cross, text_auto=True, aspect="auto",
                                  title="Warganegara × Kesalahan"), width="stretch")


# ---------------------------------------------------------------------------
# Page 5 — Tindakan & Pegawai
# ---------------------------------------------------------------------------
elif page == "Tindakan & Pegawai":
    st.title("Tindakan & Pegawai")
    bd = kpis.breakdowns(df)
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(px.bar(bd["tindakan"], x="tindakan_kod", y="bilangan",
                               title="Pecahan tindakan"), width="stretch")
    with c2:
        per_officer = df.groupby("nama_pegawai").size().sort_values(ascending=False).head(15)
        st.plotly_chart(px.bar(per_officer, title="Kes per pegawai"), width="stretch")
    per_fail = df.groupby("fail").size().sort_values(ascending=False).head(15)
    st.plotly_chart(px.bar(per_fail, title="Kes per FAIL"), width="stretch")


# ---------------------------------------------------------------------------
# Page 6 — Kualiti Data
# ---------------------------------------------------------------------------
elif page == "Kualiti Data":
    st.title("Kualiti Data")
    st.metric("Kes ditolak semasa import", money(repo.rejects_count()))
    invalid = df_all[df_all["is_valid"] == 0] if "is_valid" in df_all else df_all.iloc[0:0]
    st.subheader(f"Rekod tidak sah ({len(invalid)})")
    if not invalid.empty:
        st.dataframe(invalid[["no_reman", "issues"]].head(200), width="stretch")
    st.subheader("Ringkasan isu")
    issues = []
    for _, r in df_all.iterrows():
        for i in (r.get("issues") or []):
            issues.append(i.get("code"))
    if issues:
        st.plotly_chart(px.bar(pd.Series(issues).value_counts(), title="Kekerapan isu"),
                        width="stretch")


# ---------------------------------------------------------------------------
# Page 7 — Data Entry (E1)
# ---------------------------------------------------------------------------
elif page == "Data Entry":
    st.title("Data Entry — Rekod Reman Baharu")
    with st.form("entry"):
        c1, c2, c3 = st.columns(3)
        no_reman = c1.text_input("NO.REMAN", placeholder="26(0001)BD")
        nama = c2.text_input("NAMA")
        pegawai = c3.text_input("NAMA PEGAWAI")
        c4, c5, c6 = st.columns(3)
        jantina = c4.selectbox("JANTINA", ["LELAKI", "PEREMPUAN"])
        umur = c5.number_input("UMUR (THN)", 18, 100, 30)
        depot = c6.selectbox("DEPOT", DEPOTS)
        c7, c8, c9 = st.columns(3)
        warga = c7.selectbox("WARGANEGARA", KNOWN_NATIONALITIES)
        bangsa = c8.selectbox("BANGSA", KNOWN_BANGSA)
        tindakan = c9.selectbox("TINDAKAN", TINDAKAN_CODES)
        c10, c11, c12 = st.columns(3)
        mula = c10.date_input("Tarikh mula reman", date.today())
        tamat = c11.date_input("Tarikh tamat reman", date.today() + timedelta(days=13))
        fail = c12.text_input("FAIL", placeholder="(01)2026")
        kesalahan = st.text_input("KESALAHAN", placeholder="6(1)(C) IMMG")
        catatan = st.text_area("CATATAN", "")
        submitted = st.form_submit_button("Simpan (auto-kira semula)")

    if submitted:
        try:
            form = RemanForm(no_reman=no_reman, nama=nama, jantina=jantina, umur_thn=int(umur),
                             bangsa=bangsa, warganegara=warga, nama_pegawai=pegawai, fail=fail,
                             depot=depot, catatan=catatan, tindakan=tindakan, kesalahan=kesalahan,
                             tarikh_reman_mula=mula, tarikh_reman_tamat=tamat)
            result = ingest_form(form, repo, actor="officer", role=role)
            clear_caches()
            st.success(f"Disimpan {result['no_reman']} — risiko {result['risk_label']} "
                       f"({result['risk_score']}). {result['recommended_action']}")
            st.rerun()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Ralat: {exc}")

    st.divider()
    st.subheader("Muat naik Excel (cleaning map akan dijalankan)")
    up = st.file_uploader("Fail register (.xlsx)", type=["xlsx"])
    if up is not None and st.button("Import"):
        raw = pd.read_excel(up, dtype=str)
        summary = ingest_dataframe(raw, repo, actor="officer", role=role, source=f"upload:{up.name}")
        clear_caches()
        st.success(f"Selesai: {summary.as_dict()}")
        st.rerun()


# ---------------------------------------------------------------------------
# Page 8 — Priority Worklist (UC-2 / E7)
# ---------------------------------------------------------------------------
elif page == "Priority Worklist":
    st.title("Priority Worklist")
    if st.button("Jalankan semula enjin harian (E5+E6+E7)"):
        run_daily(repo, as_of=date.today())
        clear_caches()
        st.rerun()

    work = df[df["tindakan_kod"].ne("BEBAS DENGAN AMARAN")].sort_values(
        ["risk_score", "hari_berbaki"], ascending=[False, True])
    for _, r in work.head(30).iterrows():
        with st.expander(f"{r['no_reman']} · {r['risk_label']} ({r['risk_score']}) · "
                         f"{r['depot']} · {r['hari_berbaki']} hari"):
            st.write(f"**Cadangan tindakan:** {r['recommended_action']}")
            st.write("**Sebab skor:** " + ("; ".join(r.get("risk_reasons") or []) or "-"))
            st.write(f"Warganegara: {r['warganegara']} | Akta: {r['akta']} {r['seksyen']} | "
                     f"TINDAKAN: {r['tindakan_kod']}")
            c1, c2 = st.columns([1, 2])
            if c1.button("Terima cadangan", key=f"acc_{r['no_reman']}"):
                decision_support.log_decision(repo, r["no_reman"], r["recommended_action"],
                                              decision_support.DECISION_ACCEPT, actor=role)
                st.success("Diterima & direkod.")
            override = c2.text_input("Atau tulis tindakan lain (override)", key=f"ovr_{r['no_reman']}")
            if c2.button("Simpan override", key=f"ovb_{r['no_reman']}") and override:
                decision_support.log_decision(repo, r["no_reman"], r["recommended_action"],
                                              decision_support.DECISION_OVERRIDE,
                                              override_action=override, reason="officer override",
                                              actor=role)
                st.success("Override direkod.")


# ---------------------------------------------------------------------------
# Page 9 — Forecast (UC-3 / E8)
# ---------------------------------------------------------------------------
elif page == "Forecast":
    st.title("Ramalan Populasi Depot (UC-3)")
    fc = repo.latest_forecast()
    if fc.empty:
        st.info("Belum ada ramalan. Tekan butang di bawah untuk menjana.")
        if st.button("Jana ramalan sekarang"):
            run_daily(repo)
            clear_caches()
            st.rerun()
    else:
        for depot, grp in fc.groupby("depot"):
            grp = grp.sort_values("horizon_date")
            fig = px.line(grp, x="horizon_date", y="yhat", markers=True,
                          title=f"Ramalan kemasukan mingguan — {depot}")
            if grp["yhat_hi"].notna().any():
                fig.add_scatter(x=grp["horizon_date"], y=grp["yhat_hi"], mode="lines",
                                name="selang atas", line=dict(dash="dot"))
                fig.add_scatter(x=grp["horizon_date"], y=grp["yhat_lo"], mode="lines",
                                name="selang bawah", line=dict(dash="dot"))
            st.plotly_chart(fig, width="stretch")

    st.subheader("Amaran kapasiti")
    from smartdepot.forecast import forecaster
    warnings = forecaster.capacity_warnings(df_all)
    if warnings:
        st.table(pd.DataFrame(warnings))
    else:
        st.success("Tiada depot melebihi had kapasiti.")


# ---------------------------------------------------------------------------
# Page 10 — Reports & Audit (UC-4 / E10)
# ---------------------------------------------------------------------------
else:
    st.title("Reports & Audit")
    st.subheader("Jana laporan bulanan (UC-4)")
    c1, c2, c3 = st.columns(3)
    year = c1.number_input("Tahun", 2024, 2030, date.today().year)
    month = c2.number_input("Bulan", 1, 12, date.today().month)
    if c3.button("Jana laporan"):
        art = report_generator.generate_monthly_report(
            df_all, int(year), int(month), settings.output_dir / "laporan")
        st.session_state["report"] = art
        st.success(f"Laporan {art['period']} dijana.")
    art = st.session_state.get("report")
    if art:
        st.markdown("**Naratif (daripada nombor yang dikira sahaja):**")
        st.code(art["narrative"])
        cols = st.columns(3)
        for col, key in zip(cols, ["xlsx", "docx", "html"]):
            if art.get(key):
                col.download_button(f"Muat turun {key.upper()}",
                                    data=Path(art[key]).read_bytes(),
                                    file_name=Path(art[key]).name, key=f"dl_{key}")

    st.divider()
    st.subheader("Audit trail (E10)")
    if not reveal:
        st.info("Peranan 'officer': nama dan catatan bertopeng.")
    ev = pd.DataFrame(repo.events(100))
    st.dataframe(ev, width="stretch")
    st.subheader("Keputusan pegawai (accept / override)")
    st.dataframe(pd.DataFrame(repo.decisions(100)), width="stretch")
