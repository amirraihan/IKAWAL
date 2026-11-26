"""End-to-end tests across UC-4 Phases 1, 2, 3, and 4."""

from __future__ import annotations

import datetime as dt
import io
import os
import shutil
import tempfile
import unittest

import openpyxl

import app as main_app
from uc4.contracts import contains_forbidden_keys
from uc4.phase1_kpi.engine import build_monthly_kpi, load_records_from_sqlite
from uc4.phase2_narrative.generator import generate_narrative, trace_narrative_numbers
from uc4.phase3_reports.pdf_builder import build_monthly_pdf
from uc4.phase3_reports.xlsx_builder import build_monthly_xlsx
from uc4.phase4_ui.__main__ import create_standalone_app


class TestUC4EndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="uc4_test_")
        src_db = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ikawal.db"
        )
        self.test_db = os.path.join(self.tmpdir, "test_ikawal.db")
        if os.path.exists(src_db):
            shutil.copy2(src_db, self.test_db)
        else:
            main_app.DB_PATH = self.test_db
            main_app.init_db()

        self._prev_env_db = os.environ.get("IKAWAL_DB")
        self._prev_app_db = main_app.DB_PATH
        os.environ["IKAWAL_DB"] = self.test_db
        main_app.DB_PATH = self.test_db

    def tearDown(self):
        if self._prev_env_db is None:
            os.environ.pop("IKAWAL_DB", None)
        else:
            os.environ["IKAWAL_DB"] = self._prev_env_db
        main_app.DB_PATH = self._prev_app_db
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_phase1_infographics_and_phase2_narrative_guard(self):
        records = load_records_from_sqlite(self.test_db)
        kpi = build_monthly_kpi(records, month_ym="2026-10", ref_date=dt.date(2026, 11, 26))
        self.assertIn("infographics", kpi)
        self.assertTrue(kpi["infographics"]["pecahan_warganegara"])
        self.assertTrue(kpi["infographics"]["kesalahan_setiap_warganegara"]["rows"])
        self.assertEqual(contains_forbidden_keys(kpi), [])

        narr = generate_narrative(kpi, mode="fallback")
        self.assertTrue(narr["privacy_verified"])
        self.assertTrue(narr["numeric_guard"]["passed"], narr["numeric_guard"])
        self.assertGreaterEqual(len(narr["paragraphs"]), 3)

        # Hallucinated number must be caught by numeric traceability guard
        bad_trace = trace_narrative_numbers("Jumlah reman melonjak ke 999999 kes bulan ini.", kpi)
        self.assertFalse(bad_trace["passed"])
        self.assertIn("999999", bad_trace["untraced_numbers"])

    def test_phase3_pdf_and_xlsx_builders(self):
        records = load_records_from_sqlite(self.test_db)
        kpi = build_monthly_kpi(records, month_ym="2026-10")
        narr = generate_narrative(kpi, mode="fallback")

        pdf_bytes = build_monthly_pdf(kpi, narr, review_meta={"status": "released", "reviewed_by": "Penganalisis", "reviewed_at": "2026-11-26"})
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))
        self.assertGreater(len(pdf_bytes), 3000)

        xlsx_bytes = build_monthly_xlsx(kpi, narr, review_meta={"status": "released", "reviewed_by": "Penganalisis"})
        wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
        self.assertEqual(
            wb.sheetnames,
            [
                "1_Ringkasan_KPI",
                "2_Naratif_&_Insights",
                "3_Depot_&_MoM",
                "4_Warganegara_&_Kesalahan",
                "5_Tindakan_&_Pegawai",
                "6_UC2_UC3_&_Kualiti",
            ],
        )

    def test_phase3_and_phase4_flask_endpoints(self):
        client = main_app.app.test_client()

        # Unauthenticated API call returns 401
        r_unauth = client.get("/api/uc4/months")
        self.assertEqual(r_unauth.status_code, 401)

        # Log in as staff
        with client.session_transaction() as sess:
            sess["role"] = "staff"
            sess["name"] = "Staff Uji"

        r_page = client.get("/uc4")
        self.assertEqual(r_page.status_code, 200)
        self.assertIn(b"AI Insight", r_page.data)

        r_months = client.get("/api/uc4/months")
        self.assertEqual(r_months.status_code, 200)
        months_data = r_months.get_json()
        self.assertIn("2026-10", months_data["months"])

        # Generate report
        r_gen = client.post("/api/uc4/generate", json={"month": "2026-10", "mode": "fallback"})
        self.assertEqual(r_gen.status_code, 200)
        rep = r_gen.get_json()["report"]
        self.assertEqual(rep["status"], "draft")
        self.assertTrue(rep["numeric_guard"]["passed"])

        # Analyst edits narrative with invalid number -> release must block
        r_bad = client.put("/api/uc4/narrative", json={"month": "2026-10", "narrative_text": "Ada 888777 kes palsu."})
        self.assertEqual(r_bad.status_code, 200)
        self.assertFalse(r_bad.get_json()["report"]["numeric_guard"]["passed"])

        r_rel_fail = client.post("/api/uc4/release", json={"month": "2026-10"})
        self.assertEqual(r_rel_fail.status_code, 400)

        # Regenerate valid narrative & release
        r_gen2 = client.post("/api/uc4/generate", json={"month": "2026-10", "mode": "fallback"})
        self.assertEqual(r_gen2.status_code, 200)
        r_rel_ok = client.post("/api/uc4/release", json={"month": "2026-10"})
        self.assertEqual(r_rel_ok.status_code, 200)
        self.assertEqual(r_rel_ok.get_json()["report"]["status"], "released")

        # Export PDF & XLSX
        r_pdf = client.get("/api/uc4/export/pdf?month=2026-10")
        self.assertEqual(r_pdf.status_code, 200)
        self.assertTrue(r_pdf.data.startswith(b"%PDF-"))

        r_xlsx = client.get("/api/uc4/export/xlsx?month=2026-10")
        self.assertEqual(r_xlsx.status_code, 200)
        wb = openpyxl.load_workbook(io.BytesIO(r_xlsx.data))
        self.assertIn("1_Ringkasan_KPI", wb.sheetnames)

        # Boss role cannot edit or release, only view/export
        with client.session_transaction() as sess:
            sess["role"] = "boss"
            sess["name"] = "Boss Uji"
        self.assertEqual(client.post("/api/uc4/release", json={"month": "2026-10"}).status_code, 403)
        self.assertEqual(client.get("/api/uc4/export/pdf?month=2026-10").status_code, 200)

        # Existing main app routes still work
        self.assertEqual(client.get("/").status_code, 200)
        self.assertEqual(client.get("/app").status_code, 200)
        self.assertEqual(client.get("/api/data").status_code, 200)

    def test_phase4_standalone_app(self):
        standalone = create_standalone_app()
        c = standalone.test_client()
        self.assertEqual(c.get("/uc4").status_code, 200)
        self.assertEqual(c.get("/api/uc4/months").status_code, 200)


if __name__ == "__main__":
    unittest.main()
