"""Tests for the cleaning / code-mapping layer (pipeline stage 2)."""

from __future__ import annotations

import unittest
from datetime import date

from smartdepot.ingest import cleaning as C


class TestPeriodParsing(unittest.TestCase):
    def test_valid(self):
        s, e, err = C.parse_reman_period("01.01.2026-14.01.2026")
        self.assertIsNone(err)
        self.assertEqual(s, date(2026, 1, 1))
        self.assertEqual(e, date(2026, 1, 14))

    def test_end_before_start(self):
        s, e, err = C.parse_reman_period("14.01.2026-01.01.2026")
        self.assertEqual(err, "end_before_start")

    def test_blank(self):
        _, _, err = C.parse_reman_period("")
        self.assertEqual(err, "blank_period")


class TestNormalisers(unittest.TestCase):
    def test_nationality_variants(self):
        for raw in ("FILIPINA", " phl", "Filipinas", "BAJAU", "SULUK"):
            self.assertEqual(C.normalize_nationality(raw), "Filipina")
        self.assertEqual(C.normalize_nationality("."), "Tidak Dinyatakan")
        self.assertEqual(C.normalize_nationality("INDONESIA"), "Indonesia")

    def test_bangsa_variants(self):
        self.assertEqual(C.normalize_bangsa("VISAYA"), "Bisaya")
        self.assertEqual(C.normalize_bangsa("BISAYA"), "Bisaya")
        self.assertEqual(C.normalize_bangsa("-"), "-")

    def test_gender_flags_numbers(self):
        self.assertEqual(C.normalize_gender("LELAKI"), ("LELAKI", True))
        gender, ok = C.normalize_gender("41")
        self.assertFalse(ok)

    def test_tindakan_variants(self):
        self.assertEqual(C.classify_tindakan("USIR / RAI"), "USIR + RAI")
        self.assertEqual(C.classify_tindakan("USR"), "USIR")
        self.assertEqual(C.classify_tindakan(""), "BELUM MUKTAMAD")
        self.assertEqual(C.classify_tindakan("UJIAN DNA"), "BELUM MUKTAMAD")
        self.assertEqual(C.classify_tindakan("BEBAS DENGAN AMARAN"), "BEBAS DENGAN AMARAN")

    def test_akta_and_seksyen(self):
        self.assertEqual(C.classify_akta("6(1)( C ) Immg"), "Akta Imigresen 1959/63")
        self.assertEqual(C.classify_akta("39B ADB 1952"), "Akta Dadah Berbahaya 1952")
        self.assertEqual(C.classify_akta("SEK 411 KK"), "Kanun Keseksaan")
        self.assertEqual(C.classify_akta("Sek:15(1)(a) ADB 1952"), "Akta Dadah Berbahaya 1952")
        self.assertEqual(C.extract_seksyen("6(1)( C ) Immg"), "6(1)(C)")
        self.assertEqual(C.extract_seksyen("SEK 39A(1)ADB1952"), "39A(1)")
        self.assertEqual(C.extract_seksyen("SEKSYEN 120 (1) KK"), "120(1)")
        self.assertEqual(C.extract_seksyen("39B ADB 1952"), "")

    def test_age_band_and_repeat(self):
        self.assertEqual(C.age_band(25), "18-29")
        self.assertEqual(C.age_band(61), "60+")
        self.assertTrue(C.is_repeat("kes tangkap semula"))
        self.assertFalse(C.is_repeat("tiada"))


class TestCleanRow(unittest.TestCase):
    def test_end_to_end(self):
        raw = {
            "tarikh_tamat_reman_raw": "01.02.2026-14.02.2026", "nama": "ali bin abu",
            "jantina": "LELAKI", "umur_thn": "40", "bangsa": "VISAYA",
            "warganegara": " phl", "no_reman": " 26(0001)bd ", "dokumen": "NIL",
            "nama_pegawai": "KP RAMLI", "fail": "(01)2026", "depot": "dikk",
            "catatan": "tahan semula", "tindakan": "USIR / RAI",
            "kesalahan": "6(1)( C ) Immg",
        }
        record, issues = C.clean_row(raw)
        self.assertEqual(record["no_reman"], "26(0001)BD")
        self.assertEqual(record["warganegara"], "Filipina")
        self.assertEqual(record["bangsa"], "Bisaya")
        self.assertEqual(record["depot"], "DIKK")
        self.assertEqual(record["jantina"], "LELAKI")


class TestRealLayout(unittest.TestCase):
    """The real register uses TARIKH MASUK + a single TARIKH TAMAT REMAN."""

    def test_separate_date_columns(self):
        raw = {
            "tarikh_masuk": "02.01.2026", "tarikh_tamat_reman_raw": "15.01.2026",
            "no_reman": "26(01)BD", "nama": "X", "jantina": "PEREMPUAN",
            "umur_thn": "38", "bangsa": "TAGALOG", "warganegara": " FILIPINA",
            "fail": "(01)2026", "depot": " DIP", "catatan": "", "tindakan": "USIR/BLI",
            "kesalahan": "SEK 411 KK",
        }
        record, issues = C.clean_row(raw)
        self.assertEqual(record["tarikh_masuk"], "02.01.2026")
        self.assertEqual(record["tarikh_reman_mula"], date(2026, 1, 2))
        self.assertEqual(record["tarikh_reman_tamat"], date(2026, 1, 15))
        self.assertEqual(record["warganegara"], "Filipina")
        self.assertEqual(record["bangsa"], "Tagalog")
        self.assertEqual(record["depot"], "DIP")
        self.assertEqual(C.classify_akta(record["kesalahan"]), "Kanun Keseksaan")


if __name__ == "__main__":
    unittest.main()
