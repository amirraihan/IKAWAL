"""Tests for the reman engine (E5), risk scoring (E6) and decision support (E7)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from smartdepot.engines import decision_support, reman_engine
from smartdepot.engines.risk_scoring import label_for, score_record
from smartdepot.repository import RepanRepository

_FEATURED = {
    "no_reman": "26(0001)BD", "depot": "DIKK", "fail": "(01)2026",
    "tindakan_kod": "BELUM MUKTAMAD", "hari_berbaki": -1, "tempoh_reman": 14,
    "flag_ulang": False, "umur_thn": 40,
}


class TestRemanEngine(unittest.TestCase):
    def test_tiers(self):
        self.assertEqual(reman_engine.alert_tier(-2, "BELUM MUKTAMAD"), "overdue")
        self.assertEqual(reman_engine.alert_tier(0, "BELUM MUKTAMAD"), "due_today")
        self.assertEqual(reman_engine.alert_tier(1, "BELUM MUKTAMAD"), "d1")
        self.assertEqual(reman_engine.alert_tier(3, "BELUM MUKTAMAD"), "d3")
        self.assertEqual(reman_engine.alert_tier(10, "BELUM MUKTAMAD"), "none")

    def test_resolved_never_alerts(self):
        self.assertEqual(reman_engine.alert_tier(-5, "USIR"), "none")


class TestRiskScoring(unittest.TestCase):
    def test_overdue_pending(self):
        result = score_record(_FEATURED)
        # overdue & not final (+40) + pending (+15) = 55 -> Tinggi
        self.assertEqual(result["risk_score"], 55)
        self.assertEqual(result["risk_label"], "Tinggi")
        self.assertTrue(result["risk_reasons"])

    def test_cutoffs(self):
        self.assertEqual(label_for(60), "Kritikal")
        self.assertEqual(label_for(35), "Tinggi")
        self.assertEqual(label_for(15), "Sederhana")
        self.assertEqual(label_for(0), "Rendah")

    def test_extended_repeat_elder(self):
        rec = dict(_FEATURED, tindakan_kod="USIR", hari_berbaki=10,
                   tempoh_reman=45, flag_ulang=True, umur_thn=70)
        result = score_record(rec)
        # extended(10) + repeat(10) + age(10) = 30 -> Sederhana
        self.assertEqual(result["risk_score"], 30)
        self.assertEqual(result["risk_label"], "Sederhana")

    def test_fairness_ignores_nationality_and_race(self):
        a = score_record(dict(_FEATURED, warganegara="Filipina", bangsa="Bajau"))
        b = score_record(dict(_FEATURED, warganegara="Indonesia", bangsa="Bugis"))
        self.assertEqual(a["risk_score"], b["risk_score"])


class TestDecisionSupport(unittest.TestCase):
    def test_recommendation(self):
        rec = dict(_FEATURED, risk_label="Kritikal", alert_tier="overdue")
        self.assertIn("Segera", decision_support.recommend_action(rec))

    def test_decision_logging(self):
        with tempfile.TemporaryDirectory() as d:
            repo = RepanRepository(Path(d) / "t.db")
            decision_support.log_decision(repo, "26(0001)BD", "act", "Override",
                                          override_action="bebas", reason="test", actor="hq")
            decisions = repo.decisions()
            self.assertEqual(len(decisions), 1)
            self.assertEqual(decisions[0]["officer_decision"], "Override")
            self.assertTrue(any(e["action"] == "decision" for e in repo.events()))


if __name__ == "__main__":
    unittest.main()
