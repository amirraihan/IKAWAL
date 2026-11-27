"""Tests for the Flask <-> engine bridge (merge layer)."""

from __future__ import annotations

import unittest
from datetime import date

from smartdepot import bridge

_FLASK_ROW = {
    "nombor_reman": "26(01)BD", "nama": "X", "jantina": "LELAKI", "umur": 40,
    "bangsa": "BAJAU", "warganegara": "FILIPINA", "pegawai": "PI YUSUF",
    "nombor_fail": "(01)2026", "depot": "Papar", "tindakan": "Usir",
    "jenis_kesalahan": "SEK 5(2) IMMG", "tarikh_masuk": "2026-01-02",
    "tarikh_tamat_reman": "2026-01-15", "dokumen": "TIADA", "catatan": "",
}


class TestBridge(unittest.TestCase):
    def test_field_mapping(self):
        rec = bridge.to_engine_record(_FLASK_ROW)
        self.assertEqual(rec["no_reman"], "26(01)BD")
        self.assertEqual(rec["nama_pegawai"], "PI YUSUF")
        self.assertEqual(rec["kesalahan"], "SEK 5(2) IMMG")
        self.assertEqual(rec["depot"], "DIP")           # Papar -> DIP
        self.assertEqual(rec["tarikh_tamat_reman_raw"], "2026-01-15")

    def test_enrich_runs_engines(self):
        rec = bridge.enrich([_FLASK_ROW], as_of=date(2026, 1, 4))[0]
        self.assertEqual(rec["tindakan_kod"], "USIR")
        self.assertEqual(rec["akta"], "Akta Imigresen 1959/63")
        self.assertEqual(rec["seksyen"], "5(2)")
        self.assertEqual(rec["tempoh_reman"], 14)
        self.assertIn(rec["risk_label"], {"Kritikal", "Tinggi", "Sederhana", "Rendah"})
        self.assertTrue(rec["recommended_action"])

    def test_depot_display_roundtrip(self):
        self.assertEqual(bridge._depot("Kota Kinabalu"), "DIKK")
        self.assertEqual(bridge._depot("Papar"), "DIP")
        self.assertEqual(bridge._depot("DIKK"), "DIKK")


if __name__ == "__main__":
    unittest.main()
