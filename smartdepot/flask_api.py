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

import datetime as dt
import json
import sqlite3
from pathlib import Path

from flask import Blueprint, Response, jsonify, request, session

from . import bridge

engine_bp = Blueprint("engine", __name__)


@engine_bp.before_request
def _require_login():
    """Engine endpoints are only available to a logged-in Flask session."""
    if not session.get("role"):
        return jsonify({"error": "unauthenticated"}), 401


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
 Advisory only; officers decide. <a href="/">← back to dashboard</a></div>
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


def _esc(value) -> str:
    import html as _html

    return _html.escape(str(value if value is not None else ""))
