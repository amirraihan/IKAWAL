"""Tests for the feature layer (E3 / section 2.2)."""

from __future__ import annotations

import unittest
from datetime import date

from smartdepot.features.derive import compute_features


def _rec(**kw):
    base = {
        "no_reman": "26(0001)BD", "nama": "ALI BIN ABU", "jantina": "LELAKI",
        "umur_thn": 40, "bangsa": "Bajau", "warganegara": "Filipina",
        "dokumen": "NIL", "nama_pegawai": "KP RAMLI", "fail": "(01)2026",
        "depot": "DIKK", "catatan": "", "tindakan": "BELUM MUKTAMAD",
        "kesalahan": "6(1)(C) IMMG",
        "tarikh_reman_mula": date(2026, 1, 1),
        "tarikh_reman_tamat": date(2026, 1, 14),
    }
    base.update(kw)
    return base


class TestFeatures(unittest.TestCase):
    def test_derived_fields(self):
        rec = compute_features(_rec(), as_of=date(2026, 1, 10))
        self.assertEqual(rec["tempoh_reman"], 14)
        self.assertEqual(rec["hari_berbaki"], 4)
        self.assertEqual(rec["status_reman"], "Aktif")
        self.assertEqual(rec["akta"], "Akta Imigresen 1959/63")
        self.assertEqual(rec["seksyen"], "6(1)(C)")
        self.assertEqual(rec["tindakan_kod"], "BELUM MUKTAMAD")
        self.assertEqual(rec["kumpulan_umur"], "30-44")
        self.assertFalse(rec["flag_ulang"])

    def test_overdue_and_selesai(self):
        rec = compute_features(_rec(), as_of=date(2026, 2, 1))
        self.assertEqual(rec["status_reman"], "Tertunggak")
        rec2 = compute_features(_rec(tindakan="USIR"), as_of=date(2026, 2, 1))
        self.assertEqual(rec2["status_reman"], "Selesai")

    def test_repeat_flag_and_age(self):
        rec = compute_features(_rec(catatan="TANGKAP SEMULA", umur_thn=65),
                               as_of=date(2026, 1, 10))
        self.assertTrue(rec["flag_ulang"])
        self.assertEqual(rec["kumpulan_umur"], "60+")


if __name__ == "__main__":
    unittest.main()
