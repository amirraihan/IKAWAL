"""Flask blueprint exposing the SmartDepot engines on top of the Iringkawal app.

Registered by ``app.py`` (guarded import) so the UC-2/3/4 engines — reman alerts,
risk scoring, decision support, depot forecasting and the monthly report — become
available through the existing Flask server without changing its UI.

Endpoints
---------
GET  /engine                 small HTML page summarising the engines
GET  /api/engine/summary     KPIs + counts by risk/status
GET  /api/engine/alerts      cases raising an alert (most urgent first)
GET  /api/engine/worklist    priority-ranked cases
GET  /api/engine/forecast    weekly intake forecast per depot
POST /api/engine/decision    log an officer accept/override
GET  /api/engine/report      generate the monthly report (JSON + file paths)
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import sqlite3
from pathlib import Path

from flask import Blueprint, Response, jsonify, redirect, request, session, url_for

from . import bridge

engine_bp = Blueprint("engine", __name__)


@engine_bp.before_request
def _require_login():
    """Engine routes require a logged-in session (pages redirect, APIs 401)."""
    if not session.get("role"):
        if request.path.startswith("/api/"):
            return jsonify({"error": "unauthenticated"}), 401
        return redirect(url_for("login"))
    return None


def _db_path() -> str | Path:
    return bridge.default_db_path()


def _role() -> str:
    try:
        return session.get("role", "engine")
    except Exception:  # pragma: no cover
        return "engine"


def _log_decision(payload: dict) -> None:
    """Append the decision to the Flask app's audit table."""
    path = Path(_db_path())
    if not path.exists():
        return
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            "INSERT INTO audit (ts, user, role, action, detail) VALUES (?,?,?,?,?)",
            (dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), _role(), _role(),
             "Engine decision", json.dumps(payload, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()


@engine_bp.get("/api/engine/summary")
def api_summary():
    return jsonify(bridge.summary(_db_path()))


@engine_bp.get("/api/engine/alerts")
def api_alerts():
    data = bridge.alerts(_db_path())
    keep = ("no_reman", "nama", "depot", "warganegara", "hari_berbaki",
            "alert_tier", "risk_score", "risk_label", "recommended_action")
    return jsonify([{k: r.get(k) for k in keep} for r in data])


@engine_bp.get("/api/engine/worklist")
def api_worklist():
    limit = request.args.get("limit", default=50, type=int)
    data = bridge.worklist(_db_path(), limit=limit)
    keep = ("no_reman", "nama", "depot", "warganegara", "hari_berbaki",
            "risk_score", "risk_label", "risk_reasons", "recommended_action")
    return jsonify([{k: r.get(k) for k in keep} for r in data])


@engine_bp.get("/api/engine/forecast")
def api_forecast():
    return jsonify(bridge.forecast(_db_path()))


@engine_bp.post("/api/engine/decision")
def api_decision():
    payload = request.get_json(silent=True) or {}
    payload.setdefault("ts", dt.datetime.now().isoformat(timespec="seconds"))
    _log_decision(payload)
    return jsonify({"ok": True, "logged": payload})


@engine_bp.get("/api/engine/report")
def api_report():
    year = request.args.get("year", default=0, type=int)
    month = request.args.get("month", default=0, type=int)
    return jsonify(bridge.monthly_report(_db_path(), year=year, month=month))


@engine_bp.get("/engine")
def page():
    s = bridge.summary(_db_path())
    alerts = bridge.alerts(_db_path())[:15]
    work = bridge.worklist(_db_path(), limit=15)
    fc = bridge.forecast(_db_path())

    def rows(items, cols):
        head = "".join(f"<th>{c}</th>" for c in cols)
        body = "".join(
            "<tr>" + "".join(f"<td>{_esc(r.get(c))}</td>" for c in cols) + "</tr>"
            for r in items
        )
        return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"

    ov = s.get("overview", {})
    cards = "".join(
        f'<div class="kpi"><b>{_esc(k)}</b><span>{_esc(v)}</span></div>'
        for k, v in ov.items()
    )
    forecast_html = ""
    for f in fc:
        horizon = f.get("horizon", [])
        forecast_html += f"<h3>{_esc(f['depot'])} <small>({_esc(f['model'])})</small></h3>"
        forecast_html += rows(horizon[:6], ["week_start", "yhat", "yhat_lo", "yhat_hi"])

    html = f"""<!DOCTYPE html><html lang="ms"><head><meta charset="utf-8">
<title>SmartDepot Engines</title>
<style>
 body{{font:14px/1.5 system-ui,Segoe UI,Arial;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#12203a}}
 h1{{margin:0 0 .2rem}} .sub{{color:#5a6b86;margin-bottom:1.2rem}}
 .kpis{{display:flex;flex-wrap:wrap;gap:10px;margin:1rem 0}}
 .kpi{{border:1px solid #d9e0ec;border-radius:10px;padding:10px 14px;min-width:120px}}
 .kpi b{{display:block;font-size:11px;text-transform:uppercase;color:#5a6b86}}
 .kpi span{{font-size:20px;font-weight:700}}
 table{{border-collapse:collapse;width:100%;margin:.4rem 0 1.2rem}}
 th,td{{border:1px solid #d9e0ec;padding:6px 8px;text-align:left}} th{{background:#eef3fa}}
 a{{color:#1b4d8f}}
</style></head><body>
<h1>SmartDepot Engines</h1>
<div class="sub">UC-2 reman + risk + decision · UC-3 forecast · UC-4 report — reading the Iringkawal database.
 Advisory only; officers decide. <a href="/">← back to dashboard</a> · <a href="/uc3">UC-3 dashboard →</a></div>
<div class="kpis">{cards}</div>
<h2>Alerts (E5)</h2>{rows(alerts, ["no_reman","depot","warganegara","alert_tier","hari_berbaki","risk_label"])}
<h2>Priority worklist (E6/E7)</h2>{rows(work, ["no_reman","depot","risk_score","risk_label","recommended_action"])}
<h2>Forecast (E8)</h2>{forecast_html or "<p>No history.</p>"}
<p><a href="/api/engine/summary">summary.json</a> ·
<a href="/api/engine/alerts">alerts.json</a> ·
<a href="/api/engine/worklist">worklist.json</a> ·
<a href="/api/engine/forecast">forecast.json</a> ·
<a href="/api/engine/report">report.json</a></p>
</body></html>"""
    return Response(html, mimetype="text/html")


@engine_bp.get("/api/engine/forecast/dashboard")
def api_forecast_dashboard():
    return jsonify(bridge.forecast_dashboard(_db_path()))


@engine_bp.get("/uc3")
def uc3_page():
    """Dedicated UC-3 dashboard: depot population / intake forecasting."""
    import html as _html
    import json as _json

    data = bridge.forecast_dashboard(_db_path())
    depots = data.get("depots", [])
    real = [d for d in depots if d["depot"] != "SEMUA"]
    nxt = round(sum((d.get("next_week") or 0) for d in real), 1)
    horizon_total = round(sum((d.get("total_horizon") or 0) for d in real), 1)
    payload = _json.dumps(data, ensure_ascii=False)

    logo_path = Path(__file__).resolve().parent / "assets" / "uc3_logo.png"
    if logo_path.exists():
        _src = "data:image/png;base64," + base64.b64encode(logo_path.read_bytes()).decode("ascii")
        logo_html = f'<img class="uc3-logo" alt="Iringkawal" src="{_src}">'
        kpi_ico = f'<img class="kpi-ico" alt="" src="{_src}">'
    else:
        logo_html = '<div class="crest">IB</div>'
        kpi_ico = ''

    cards = "".join(
        f'<section class="card"><div class="chead"><h3>{_html.escape(d["display"])}</h3>'
        f'<span class="badge">{_html.escape(str(d["model"]))}'
        f'{" · MAPE " + str(round(d["mape"] * 100, 1)) + "%" if d.get("mape") is not None else ""}</span></div>'
        f'<div class="cstats"><div><b>Minggu depan</b><span>{d.get("next_week")}</span></div>'
        f'<div><b>Jumlah horizon</b><span>{d.get("total_horizon")}</span></div></div>'
        f'<div class="wrap"><canvas id="c_{_html.escape(d["depot"])}"></canvas></div></section>'
        for d in depots
    )

    cap_rows = "".join(
        f'<tr><td>{_html.escape(c["display"])}</td><td class="n">{c["headcount"]}</td>'
        f'<td class="n">{c["capacity"]}</td>'
        f'<td><div class="bar"><span style="width:{min(int(c["pct"] * 100), 100)}%'
        f'{" ;background:#E5484D" if c["pct"] >= 0.9 else ""}"></span></div></td>'
        f'<td class="n">{round(c["pct"] * 100)}%</td></tr>'
        for c in data.get("capacity", [])
    )

    html = f"""<!DOCTYPE html><html lang="ms"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>UC-3 · Ramalan Populasi Depot — SmartDepot</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
 :root{{--ink:#12203a;--muted:#5a6b86;--line:#d9e0ec;--bg:#f4f7fc;--brand:#1b4d8f;--brand2:#2f7dc4;}}
 *{{box-sizing:border-box;}}
 body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 "Segoe UI",system-ui,Arial,sans-serif;}}
 .wrap-page{{max-width:1100px;margin:0 auto;padding:28px 20px 60px;}}
 header.hero{{background:linear-gradient(135deg,#17335c,#1b4d8f 55%,#2f7dc4);color:#fff;border-radius:16px;padding:26px 30px;}}
 header.hero h1{{margin:0 0 6px;font-size:24px;}} .eyebrow{{text-transform:uppercase;letter-spacing:.16em;font-size:11.5px;font-weight:700;opacity:.85;margin:0 0 6px;}}
 header.hero p{{margin:0;opacity:.95;max-width:80ch;}}
 header.hero a{{color:#dbe9ff;}}
 .brandrow{{display:flex;align-items:center;gap:16px;margin-bottom:10px;}}
 .uc3-logo{{height:52px;width:auto;background:#fff;border-radius:10px;padding:6px 10px;box-shadow:0 3px 10px rgba(0,0,0,.18);}}
 .crest{{width:46px;height:46px;border-radius:10px;background:#fff;color:#17335c;font-weight:800;display:flex;align-items:center;justify-content:center;font-size:18px;}}
 .kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:18px 0;}}
 .kpi{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 16px;}}
 .kpi b{{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);}}
 .kpi span{{font-size:1.8rem;font-weight:800;color:#12203a;}}
 .kpi-ico{{display:block;height:20px;width:auto;margin:0 0 8px;}}
 .card{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin:16px 0;}}
 .chead{{display:flex;justify-content:space-between;align-items:center;}} .chead h3{{margin:0;}}
 .badge{{background:#e8f0fb;color:var(--brand);border-radius:999px;padding:3px 12px;font-size:.72rem;font-weight:700;}}
 .cstats{{display:flex;gap:26px;margin:10px 0 4px;}} .cstats b{{display:block;font-size:10.5px;text-transform:uppercase;color:var(--muted);letter-spacing:.5px;}} .cstats span{{font-size:1.3rem;font-weight:800;}}
 .wrap{{position:relative;height:280px;}}
 table{{width:100%;border-collapse:collapse;font-size:.86rem;}} th,td{{border:1px solid var(--line);padding:7px 10px;text-align:left;}} th{{background:#eef3fa;}}
 td.n{{text-align:right;font-variant-numeric:tabular-nums;}}
 .bar{{position:relative;height:12px;background:#eaf0f8;border-radius:99px;overflow:hidden;min-width:120px;}} .bar span{{position:absolute;inset:0 auto 0 0;background:linear-gradient(90deg,#0d7a5f,#14c8b6);border-radius:99px;}}
 .links a{{color:var(--brand);margin-right:14px;}}
 @media(max-width:760px){{.kpis{{grid-template-columns:repeat(2,1fr);}}}}
</style></head><body><div class="wrap-page">
<header class="hero">
  <div class="brandrow">{logo_html}<div>
    <p class="eyebrow">Use case 3 · E8 · UC-3</p>
    <h1>Ramalan Populasi Depot</h1>
  </div></div>
  <p>Ramalan kemasukan reman mingguan per depot (dan keseluruhan). Garis pepejal = sejarah sebenar;
     garis putus-putus = ramalan; jalur = selang keyakinan 95%. Model dipilih automatik mengikut ralat back-test (MAPE).
     <br><span class="links"><a href="/">← Dashboard</a><a href="/engine">Enjin (UC-2/3/4)</a><a href="/api/engine/forecast/dashboard">JSON</a></span></p>
</header>

<div class="kpis">
  <div class="kpi">{kpi_ico}<b>Depot diramal</b><span>{len(real)}</span></div>
  <div class="kpi">{kpi_ico}<b>Kemasukan minggu depan</b><span>{nxt:g}</span></div>
  <div class="kpi">{kpi_ico}<b>Jumlah {len(depots[0]['forecast']) if depots else 0} minggu</b><span>{horizon_total:g}</span></div>
  <div class="kpi">{kpi_ico}<b>Penduduk depot semasa</b><span>{data.get('total_headcount', 0)}</span></div>
</div>

<section class="card">
  <div class="chead"><h3>Kapasiti &amp; pendudukan depot</h3>
    <span class="badge">{len(data.get('warnings', []))} amaran kapasiti</span></div>
  <table><thead><tr><th>Depot</th><th class="n">Penduduk</th><th class="n">Kapasiti</th><th>Penggunaan</th><th class="n">%</th></tr></thead>
  <tbody>{cap_rows or '<tr><td colspan="5">Tiada data kapasiti.</td></tr>'}</tbody></table>
</section>

{cards or '<section class="card">Tiada sejarah mencukupi untuk ramalan.</section>'}

<p style="color:var(--muted);font-size:12.5px">Dijana oleh enjin SmartDepot (E8). Semua output adalah nasihat; pegawai membuat keputusan.</p>
</div>
<script>
const DATA = {payload};
const PAL = ["#1D6FE0","#0FB5A6","#2E86FF","#14C8B6","#F59E0B","#8B5CF6"];
if (typeof Chart !== "undefined") {{
  DATA.depots.forEach(function(d, i){{
    var el = document.getElementById("c_" + d.depot);
    if(!el) return;
    var hist = d.history || [], fc = d.forecast || [];
    var labels = hist.map(function(h){{return h.week.slice(5);}}).concat(fc.map(function(f){{return f.week.slice(5);}}));
    var hl = hist.length, fl = fc.length;
    var actual = hist.map(function(h){{return h.n;}}).concat(new Array(fl).fill(null));
    var pred = new Array(hl).fill(null);
    if(hl) pred[hl-1] = hist[hl-1].n;
    fc.forEach(function(f){{ pred.push(f.yhat); }});
    var hi = new Array(hl).fill(null).concat(fc.map(function(f){{return f.hi;}}));
    var lo = new Array(hl).fill(null).concat(fc.map(function(f){{return f.lo;}}));
    var col = PAL[i % PAL.length];
    new Chart(el.getContext("2d"), {{
      type:"line",
      data:{{ labels:labels, datasets:[
        {{ label:"Sebenar", data:actual, borderColor:"#12203a", backgroundColor:"transparent", tension:.3, borderWidth:2, pointRadius:2 }},
        {{ label:"Ramalan", data:pred, borderColor:col, backgroundColor:"transparent", borderDash:[6,4], tension:.3, borderWidth:2.5, pointRadius:3 }},
        {{ label:"Selang atas", data:hi, borderColor:"rgba(47,125,196,.45)", backgroundColor:"transparent", borderWidth:1, pointRadius:0 }},
        {{ label:"Selang bawah", data:lo, borderColor:"rgba(47,125,196,.45)", backgroundColor:"transparent", borderWidth:1, pointRadius:0, fill:"-1" }}
      ]}},
      options:{{ responsive:true, maintainAspectRatio:false, interaction:{{mode:"index",intersect:false}},
        plugins:{{ legend:{{ position:"bottom", labels:{{ boxWidth:12, filter:function(it){{return it.text!=="Selang atas" && it.text!=="Selang bawah";}} }} }} }},
        scales:{{ y:{{ beginAtZero:true, ticks:{{precision:0}}, grid:{{color:"#EEF3FA"}} }}, x:{{ grid:{{display:false}} }} }} }}
    }});
  }});
}}
</script>
</body></html>"""
    return Response(html, mimetype="text/html")


def _esc(value) -> str:
    import html as _html

    return _html.escape(str(value if value is not None else ""))
