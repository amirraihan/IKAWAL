"""Unit tests for UC-4 Phase 1 (KPI snapshot, privacy guard, MoM & insights)."""

from __future__ import annotations

import datetime as dt
import os
import unittest

from uc4.contracts import contains_forbidden_keys
from uc4.phase1_kpi.engine import (
    build_monthly_kpi,
    classify_act,
    load_records_from_sqlite,
    normalize_section,
)


def _sample_records() -> list[dict]:
    return [
        {
            "id": "1",
            "nama": "RAHSIA INDIVIDU A",
            "jantina": "Lelaki",
            "umur": 28,
            "bangsa": "Bajau",
            "warganegara": "Filipina",
            "jenis_kesalahan": "6(1)( C ) Immg",
            "nombor_reman": "26(0001)BD",
            "nombor_fail": "(01)2026",
            "depot": "Kota Kinabalu",
            "pegawai": "Insp. Ahmad",
            "tarikh_masuk": "2026-09-10",
            "tarikh_tamat_reman": "2026-09-23",
            "tindakan": "Usir",
            "surat_rayuan": "Tiada",
            "tarikh_dibebaskan": "",
            "catatan": "IC 900101-12-5555",
        },
        {
            "id": "2",
            "nama": "RAHSIA INDIVIDU B",
            "jantina": "Perempuan",
            "umur": 35,
            "bangsa": "Bugis",
            "warganegara": "Indonesia",
            "jenis_kesalahan": "Sek:15(1)(a) ADB 1952",
            "nombor_reman": "26(0002)BD",
            "nombor_fail": "(02)2026",
            "depot": "Papar",
            "pegawai": "Sgt. Siti",
            "tarikh_masuk": "2026-10-01",
            "tarikh_tamat_reman": "2026-10-14",
            "tindakan": "Usir",
            "surat_rayuan": "Diterima",
            "tarikh_dibebaskan": "",
            "catatan": "TANGKAP SEMULA",
        },
        {
            "id": "3",
            "nama": "RAHSIA INDIVIDU C",
            "jantina": "Lelaki",
            "umur": 62,
            "bangsa": "Suluk",
            "warganegara": "Filipina",
            "jenis_kesalahan": "SEK 411 KK",
            "nombor_reman": "",
            "nombor_fail": "(03)2026",
            "depot": "Papar",
            "pegawai": "Sgt. Siti",
            "tarikh_masuk": "2026-10-15",
            "tarikh_tamat_reman": "2026-10-10",  # anomalous end < start
            "tindakan": "Bebas",
            "surat_rayuan": "Tiada",
            "tarikh_dibebaskan": "2026-10-16",
            "catatan": "",
        },
    ]


class TestUC4Phase1(unittest.TestCase):
    def test_act_and_section_normalization(self):
        self.assertEqual(classify_act("6(1)( C ) Immg"), "Akta Imigresen 1959/63")
        self.assertEqual(classify_act("Sek:15(1)(a) ADB 1952"), "Akta Dadah Berbahaya 1952")
        self.assertEqual(classify_act("SEK 411 KK"), "Kanun Keseksaan")
        self.assertEqual(normalize_section("6(1)( C ) Immg"), "6(1)(C) IMMG")
        self.assertEqual(normalize_section("SEK 15(1)© IMMG"), "SEK 15(1)(C) IMMG")

    def test_kpi_snapshot_mom_and_privacy_guard(self):
        recs = _sample_records()
        payload = build_monthly_kpi(recs, month_ym="2026-10", ref_date=dt.date(2026, 10, 12))

        self.assertEqual(payload["month"], "2026-10")
        self.assertEqual(payload["month_label"], "Oktober 2026")
        self.assertEqual(payload["kpis"]["total_reman"], 2)
        self.assertEqual(payload["kpis"]["bebas"], 1)
        self.assertEqual(payload["kpis"]["aktif"], 1)
        self.assertEqual(payload["kpis"]["urgent_atau_tertunggak"], 1)
        self.assertEqual(payload["kpis"]["kualiti_data"]["nombor_reman_kosong"], 1)
        self.assertEqual(payload["kpis"]["kualiti_data"]["tarikh_tamat_sebelum_masuk"], 1)
        self.assertEqual(payload["mom"]["prev_total_reman"], 1)
        self.assertEqual(payload["mom"]["total_delta"], 1)
        self.assertEqual(payload["mom"]["total_pct_change"], 100.0)

        # Ensure zero PII keys or values leaked
        self.assertEqual(contains_forbidden_keys(payload), [])
        serialized = str(payload)
        self.assertNotIn("RAHSIA INDIVIDU", serialized)
        self.assertNotIn("900101-12-5555", serialized)
        self.assertNotIn("26(0002)BD", serialized)

    def test_uc2_uc3_adapter_override(self):
        recs = _sample_records()
        payload = build_monthly_kpi(
            recs,
            month_ym="2026-10",
            uc2_summary={"kritikal_count": 4},
            uc3_forecast={"next_month_intake": 210},
        )
        self.assertTrue(payload["uc2_summary"]["integrated"])
        self.assertEqual(payload["uc2_summary"]["kritikal_count"], 4)
        self.assertTrue(payload["uc3_forecast"]["integrated"])
        self.assertEqual(payload["uc3_forecast"]["next_month_intake"], 210)

    def test_real_sqlite_db_if_present(self):
        db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ikawal.db"
        )
        if not os.path.exists(db_path):
            self.skipTest("ikawal.db not present")
        recs = load_records_from_sqlite(db_path)
        payload = build_monthly_kpi(recs, month_ym="2026-10", ref_date=dt.date(2026, 11, 26))
        self.assertEqual(payload["kpis"]["total_reman"], 250)
        self.assertEqual(payload["mom"]["prev_total_reman"], 205)
        self.assertEqual(contains_forbidden_keys(payload), [])


if __name__ == "__main__":
    unittest.main()
