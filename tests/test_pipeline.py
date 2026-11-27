"""End-to-end tests for the pipeline (stages 1-6)."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from smartdepot.ingest.loader import ingest_dataframe
from smartdepot.pipeline import process_record, run_daily, run_monthly
from smartdepot.repository import RepanRepository


def _record(**kw):
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


class TestProcessRecord(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = RepanRepository(Path(self._tmp.name) / "t.db")

    def tearDown(self):
        self._tmp.cleanup()

    def test_on_save_chain(self):
        rec = process_record(_record(), self.repo, as_of=date(2026, 1, 1))
        self.assertEqual(rec["tempoh_reman"], 14)
        self.assertIn(rec["risk_label"], {"Kritikal", "Tinggi", "Sederhana", "Rendah"})
        self.assertEqual(rec["is_valid"], 1)

        stored = self.repo.get_reman("26(0001)BD")
        self.assertEqual(stored["no_reman"], "26(0001)BD")
        self.assertEqual(stored["akta"], "Akta Imigresen 1959/63")
        self.assertTrue(any(e["action"] == "create" for e in self.repo.events()))

    def test_ingest_rejects_bad_rows(self):
        raw = pd.DataFrame([
            {"TARIKH TAMAT REMAN": "01.02.2026-14.02.2026", "NAMA": "A", "JANTINA": "LELAKI",
             "UMUR (THN)": "30", "BANGSA": "Bajau", "WARGANEGARA": "FILIPINA",
             "NO.REMAN": "26(0002)BD", "DOKUMEN": "NIL", "NAMA PEGAWAI": "KP RAMLI",
             " FAIL": "(01)2026", "DEPOT": "DIP", "CATATAN": "", "TINDAKAN": "USIR",
             "KESALAHAN": "6(1)(C) IMMG"},
            {"TARIKH TAMAT REMAN": "14.02.2026-01.02.2026", "NAMA": "B", "JANTINA": "LELAKI",
             "UMUR (THN)": "30", "BANGSA": "Bajau", "WARGANEGARA": "FILIPINA",
             "NO.REMAN": "26(0003)BD", "DOKUMEN": "NIL", "NAMA PEGAWAI": "KP RAMLI",
             " FAIL": "(01)2026", "DEPOT": "DIP", "CATATAN": "", "TINDAKAN": "USIR",
             "KESALAHAN": "6(1)(C) IMMG"},  # end before start -> reject
            {"TARIKH TAMAT REMAN": "01.02.2026-14.02.2026", "NAMA": "C", "JANTINA": "LELAKI",
             "UMUR (THN)": "30", "BANGSA": "Bajau", "WARGANEGARA": "FILIPINA",
             "NO.REMAN": "", "DOKUMEN": "NIL", "NAMA PEGAWAI": "KP RAMLI",
             " FAIL": "(01)2026", "DEPOT": "DIP", "CATATAN": "", "TINDAKAN": "USIR",
             "KESALAHAN": "6(1)(C) IMMG"},  # blank key -> reject
        ])
        summary = ingest_dataframe(raw, self.repo, actor="test")
        self.assertEqual(summary.loaded, 1)
        self.assertEqual(summary.rejected, 2)
        self.assertEqual(self.repo.count(), 1)

    def test_daily_and_monthly(self):
        process_record(_record(), self.repo, as_of=date(2026, 1, 1))
        daily = run_daily(self.repo, as_of=date(2026, 1, 1))
        self.assertIn("alerts", daily)
        art = run_monthly(self.repo, 2026, 1)
        self.assertTrue(Path(art["xlsx"]).exists())
        self.assertIn("LAPORAN BULANAN", art["narrative"])


if __name__ == "__main__":
    unittest.main()
