"""Standalone Flask runner for UC-4 Phase 4 UI (development/isolated demo).

Usage:
    python -m uc4.phase4_ui
"""

from __future__ import annotations

import os
from flask import Flask, redirect, session

from uc4.phase3_reports.blueprint import uc4_bp


def create_standalone_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("IKAWAL_SECRET", "uc4-standalone-dev")

    @app.before_request
    def _dev_session():
        if "role" not in session:
            session["role"] = "staff"
            session["name"] = "Penganalisis UC-4 (Standalone)"

    @app.route("/")
    def root():
        return redirect("/uc4")

    app.register_blueprint(uc4_bp)
    return app


if __name__ == "__main__":
    standalone = create_standalone_app()
    port = int(os.environ.get("UC4_PORT", "5054"))
    print(f"UC-4 Standalone UI running at http://127.0.0.1:{port}/uc4")
    standalone.run(host="127.0.0.1", port=port, debug=False)
