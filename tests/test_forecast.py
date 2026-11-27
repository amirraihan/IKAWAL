"""Tests for the forecaster (E8 / UC-3)."""

from __future__ import annotations

import unittest
from datetime import date, timedelta

import pandas as pd

from smartdepot.forecast.forecaster import (
    current_headcount, forecast_series, weekly_intake,
)


def _df(weeks: int = 20) -> pd.DataFrame:
    rows = []
    start = date(2026, 1, 1)
    for i in range(weeks):
        for _ in range(5):
            d = start + timedelta(weeks=i)
            rows.append({"depot": "DIKK", "tarikh_reman_mula": d.isoformat(),
                         "tarikh_reman_tamat": (d + timedelta(days=13)).isoformat()})
    return pd.DataFrame(rows)


class TestForecaster(unittest.TestCase):
    def test_weekly_intake(self):
        series = weekly_intake(_df(4), "DIKK")
        self.assertEqual(series.sum(), 20)
        self.assertEqual(len(series), 4)

    def test_forecast_horizon(self):
        series = weekly_intake(_df(20), "DIKK")
        series.name = "DIKK"
        result = forecast_series(series, horizon=6)
        self.assertEqual(len(result.horizon), 6)
        self.assertTrue((result.horizon["yhat"] >= 0).all())

    def test_headcount(self):
        head = current_headcount(_df(20), as_of=date(2026, 5, 1))
        self.assertIn("DIKK", head)


if __name__ == "__main__":
    unittest.main()
