"""Flask Blueprint exposing UC-4 API endpoints and the /uc4 dashboard route."""

from __future__ import annotations

import datetime as dt
import io
import os
import sqlite3
from functools import wraps

from flask import Blueprint, jsonify, redirect, render_template, request, send_file, session, url_for

from uc4.phase1_kpi.engine import (
    DEFAULT_DB_PATH,
    available_months,
    build_monthly_kpi,
    load_records_from_sqlite,
)
from uc4.phase2_narrative.generator import generate_narrative, trace_narrative_numbers
from uc4.phase3_reports.pdf_builder import build_monthly_pdf
from uc4.phase3_reports.store import (
    get_saved_report,
    list_saved_statuses,
    release_report,
    save_report_draft,
    update_report_narrative,
)
from uc4.phase3_reports.xlsx_builder import build_monthly_xlsx

PHASE4_TEMPLATES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "phase4_ui",
    "templates",
)

uc4_bp = Blueprint("uc4", __name__, template_folder=PHASE4_TEMPLATES)

ROLE_CAN = {
    "staff": {"view": True, "edit": True, "export": True},
    "penyelia": {"view": True, "edit": True, "export": True},
    "boss": {"view": True, "edit": False, "export": True},
}


def _db_path() -> str:
    return os.environ.get("IKAWAL_DB", DEFAULT_DB_PATH)


def _current_user() -> dict:
    role = session.get("role") or "staff"
    return {
        "role": role,
        "name": session.get("name") or role.title(),
        "can": ROLE_CAN.get(role, {"view": True, "edit": False, "export": True}),
    }


def _uc4_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("role"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Sesi tamat. Sila log masuk semula."}), 401
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def _write_audit(action: str, detail: str) -> None:
    path = _db_path()
    if not os.path.exists(path):
        return
    u = _current_user()
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "INSERT INTO audit (ts, user, role, action, detail) VALUES (?,?,?,?,?)",
            (ts, u["name"], u["role"], action, detail),
        )
        conn.commit()
    except sqlite3.Error:
        pass
    finally:
        conn.close()


def _load_or_build_report(month_ym: str | None, mode: str = "auto", force_regen: bool = False) -> dict:
    db_file = _db_path()
    records = load_records_from_sqlite(db_file)
    months = available_months(records)
    target = month_ym or (months[-1] if months else dt.date.today().strftime("%Y-%m"))

    if not force_regen:
        saved = get_saved_report(target, db_path=db_file)
        if saved is not None:
            return saved

    kpi_payload = build_monthly_kpi(records, month_ym=target)
    narrative_res = generate_narrative(kpi_payload, mode=mode)
    return save_report_draft(kpi_payload, narrative_res, db_path=db_file)


@uc4_bp.route("/uc4")
@_uc4_login_required
def uc4_page():
    return render_template("uc4_dashboard.html", user=_current_user())


@uc4_bp.route("/api/uc4/months")
@_uc4_login_required
def api_uc4_months():
    db_file = _db_path()
    records = load_records_from_sqlite(db_file)
    months = available_months(records)
    statuses = list_saved_statuses(db_file)
    return jsonify({
        "months": months,
        "default_month": months[-1] if months else dt.date.today().strftime("%Y-%m"),
        "saved": statuses,
    })


@uc4_bp.route("/api/uc4/report")
@_uc4_login_required
def api_uc4_get_report():
    month = request.args.get("month") or None
    report = _load_or_build_report(month, mode="auto", force_regen=False)
    return jsonify({"report": report, "user": _current_user()})


@uc4_bp.route("/api/uc4/generate", methods=["POST"])
@_uc4_login_required
def api_uc4_generate():
    if not _current_user()["can"]["edit"]:
        return jsonify({"error": "Peranan anda hanya mempunyai akses lihat & eksport."}), 403
    data = request.get_json(silent=True) or {}
    month = data.get("month") or None
    mode = data.get("mode") or "auto"
    report = _load_or_build_report(month, mode=mode, force_regen=True)
    _write_audit("UC-4 Jana Laporan", f"{report['month_label']} (mode={report['narrative_mode']})")
    return jsonify({"report": report})


@uc4_bp.route("/api/uc4/narrative", methods=["PUT"])
@_uc4_login_required
def api_uc4_update_narrative():
    if not _current_user()["can"]["edit"]:
        return jsonify({"error": "Peranan anda tiada akses menyunting naratif."}), 403
    data = request.get_json(silent=True) or {}
    month = (data.get("month") or "").strip()
    text = (data.get("narrative_text") or "").strip()
    if not month or not text:
        return jsonify({"error": "Bulan dan teks naratif diperlukan."}), 400

    db_file = _db_path()
    existing = get_saved_report(month, db_path=db_file)
    if existing is None:
        existing = _load_or_build_report(month, mode="auto", force_regen=True)

    guard = trace_narrative_numbers(text, existing["kpi_payload"])
    updated = update_report_narrative(month, text, guard, db_path=db_file)
    _write_audit("UC-4 Sunting Naratif", f"{month} (guard={guard['passed']})")
    return jsonify({"report": updated})


@uc4_bp.route("/api/uc4/release", methods=["POST"])
@_uc4_login_required
def api_uc4_release():
    if not _current_user()["can"]["edit"]:
        return jsonify({"error": "Peranan anda tiada akses mengesahkan laporan."}), 403
    data = request.get_json(silent=True) or {}
    month = (data.get("month") or "").strip()
    if not month:
        return jsonify({"error": "Parameter bulan diperlukan."}), 400

    db_file = _db_path()
    existing = get_saved_report(month, db_path=db_file)
    if existing is None:
        return jsonify({"error": "Laporan draf belum dijana untuk bulan ini."}), 404

    guard = trace_narrative_numbers(existing["narrative_text"], existing["kpi_payload"])
    if not guard["passed"] and not data.get("allow_mismatch"):
        return jsonify({
            "error": f"Semakan angka mengesan nombor tidak berpadanan: {guard['untraced_numbers']}. Sila semak naratif dahulu.",
            "numeric_guard": guard,
        }), 400

    reviewer = _current_user()["name"]
    released = release_report(month, reviewer_name=reviewer, db_path=db_file)
    _write_audit("UC-4 Sahkan Laporan", f"{month} disahkan oleh {reviewer}")
    return jsonify({"report": released})


@uc4_bp.route("/api/uc4/export/pdf")
@_uc4_login_required
def api_uc4_export_pdf():
    if not _current_user()["can"]["export"]:
        return jsonify({"error": "Tiada akses eksport."}), 403
    month = request.args.get("month") or None
    report = _load_or_build_report(month, mode="auto", force_regen=False)
    narrative_res = {
        "mode": report["narrative_mode"],
        "provider": report["provider"],
        "numeric_guard": report["numeric_guard"],
        "narrative_text": report["narrative_text"],
        "paragraphs": [p.strip() for p in report["narrative_text"].split("\n\n") if p.strip()],
    }
    pdf_bytes = build_monthly_pdf(report["kpi_payload"], narrative_res, review_meta=report)
    _write_audit("UC-4 Eksport PDF", f"{report['month_label']} ({report['status']})")
    fname = f"IKAWAL_UC4_Laporan_{report['month']}.pdf"
    return send_file(io.BytesIO(pdf_bytes), as_attachment=True, download_name=fname, mimetype="application/pdf")


@uc4_bp.route("/api/uc4/export/xlsx")
@_uc4_login_required
def api_uc4_export_xlsx():
    if not _current_user()["can"]["export"]:
        return jsonify({"error": "Tiada akses eksport."}), 403
    month = request.args.get("month") or None
    report = _load_or_build_report(month, mode="auto", force_regen=False)
    narrative_res = {
        "mode": report["narrative_mode"],
        "provider": report["provider"],
        "numeric_guard": report["numeric_guard"],
        "narrative_text": report["narrative_text"],
        "paragraphs": [p.strip() for p in report["narrative_text"].split("\n\n") if p.strip()],
    }
    xlsx_bytes = build_monthly_xlsx(report["kpi_payload"], narrative_res, review_meta=report)
    _write_audit("UC-4 Eksport XLSX", f"{report['month_label']} ({report['status']})")
    fname = f"IKAWAL_UC4_Lampiran_{report['month']}.xlsx"
    return send_file(
        io.BytesIO(xlsx_bytes),
        as_attachment=True,
        download_name=fname,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
