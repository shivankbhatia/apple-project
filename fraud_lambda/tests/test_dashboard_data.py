"""Tests for the Phase 8 dashboard data module (load_report, load_clicks, alerts,
load_batch_scored, campaign_fraud_rates, publisher_fraud_rates)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))
from data import (
    alerts,
    campaign_fraud_rates,
    load_batch_scored,
    load_clicks,
    load_report,
    publisher_fraud_rates,
)


class LoadReportTests(unittest.TestCase):
    def test_missing_file_returns_none(self) -> None:
        self.assertIsNone(load_report(Path("/tmp/does-not-exist-phase-8-report.json")))

    def test_loads_valid_report(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "metrics.json"
            p.write_text(json.dumps({"matched_clicks": 42}))
            self.assertEqual(load_report(p)["matched_clicks"], 42)


class LoadClicksTests(unittest.TestCase):
    def test_missing_file_returns_empty(self) -> None:
        self.assertTrue(load_clicks(Path("/tmp/does-not-exist-clicks.csv")).empty)

    def test_loads_and_parses_timestamps(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "clicks.csv"
            pd.DataFrame({
                "click_id": ["x"],
                "speed_flagged": [1],
                "click_time": ["2017-11-06 10:00:00"],
                "speed_probability": [0.9],
            }).to_csv(p, index=False)
            df = load_clicks(p)
            self.assertFalse(df.empty)
            self.assertTrue(pd.api.types.is_datetime64_any_dtype(df["click_time"]))


class AlertsTests(unittest.TestCase):
    def test_empty_dataframe_returns_empty(self) -> None:
        self.assertTrue(alerts(pd.DataFrame(), 10).empty)

    def test_returns_most_recent_first(self) -> None:
        df = pd.DataFrame({
            "click_id": ["old", "new"],
            "speed_flagged": [1, 1],
            "click_time": pd.to_datetime(["2017-01-01", "2017-01-02"], utc=True),
            "speed_probability": [0.8, 0.9],
        })
        result = alerts(df, limit=1)
        self.assertEqual(result.iloc[0]["click_id"], "new")

    def test_limit_respected(self) -> None:
        n = 20
        df = pd.DataFrame({
            "click_id": [str(i) for i in range(n)],
            "speed_flagged": [1] * n,
            "speed_probability": [0.9] * n,
        })
        self.assertEqual(len(alerts(df, limit=5)), 5)


class LoadBatchScoredTests(unittest.TestCase):
    def test_missing_file_returns_empty(self) -> None:
        self.assertTrue(load_batch_scored(Path("/tmp/does-not-exist.parquet")).empty)

    def test_loads_parquet_and_selects_columns(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "batch.parquet"
            pd.DataFrame({
                "click_id": ["a", "b"],
                "campaign_id": [1, 2],
                "publisher_id": [10, 20],
                "batch_fraud_probability": [0.9, 0.1],
                "batch_is_flagged": [1, 0],
                "is_fraud": [1, 0],
                "extra_col": ["x", "y"],   # should be dropped
            }).to_parquet(p, index=False)
            df = load_batch_scored(p)
            self.assertEqual(list(df.columns), [
                "click_id", "campaign_id", "publisher_id",
                "batch_fraud_probability", "batch_is_flagged", "is_fraud",
            ])
            self.assertEqual(len(df), 2)

    def test_flagged_column_is_int(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "batch.parquet"
            pd.DataFrame({
                "click_id": ["a"],
                "campaign_id": [1],
                "publisher_id": [1],
                "batch_fraud_probability": [0.9],
                "batch_is_flagged": [np.nan],
                "is_fraud": [0],
            }).to_parquet(p, index=False)
            df = load_batch_scored(p)
            self.assertEqual(df["batch_is_flagged"].iloc[0], 0)
            self.assertEqual(df["batch_is_flagged"].dtype, int)


class CampaignPublisherFraudRatesTests(unittest.TestCase):
    def _make_df(self) -> pd.DataFrame:
        return pd.DataFrame({
            "click_id": list("abcde"),
            "campaign_id": [1, 1, 2, 2, 2],
            "publisher_id": [10, 10, 20, 20, 20],
            "batch_fraud_probability": [0.9, 0.1, 0.8, 0.05, 0.7],
            "batch_is_flagged":        [1,   0,   1,   0,    1],
            "is_fraud":                [1,   0,   1,   0,    0],
        })

    def test_campaign_rates_sorted_by_flag_rate_descending(self) -> None:
        df = self._make_df()
        result = campaign_fraud_rates(df)
        self.assertEqual(list(result.columns),
                         ["campaign_id", "total_clicks", "flagged",
                          "confirmed_fraud", "mean_score", "fraud_rate", "flag_rate"])
        # campaign 2: 2/3 flagged > campaign 1: 1/2 flagged
        self.assertEqual(result.iloc[0]["campaign_id"], 2)

    def test_publisher_rates_sorted_by_flag_rate_descending(self) -> None:
        df = self._make_df()
        result = publisher_fraud_rates(df)
        self.assertIn("publisher_id", result.columns)
        self.assertIn("flag_rate", result.columns)

    def test_flag_rate_in_unit_interval(self) -> None:
        df = self._make_df()
        for rate_df in (campaign_fraud_rates(df), publisher_fraud_rates(df)):
            self.assertTrue((rate_df["flag_rate"] >= 0).all())
            self.assertTrue((rate_df["flag_rate"] <= 1).all())

    def test_empty_input_returns_empty(self) -> None:
        empty = pd.DataFrame(columns=[
            "click_id", "campaign_id", "publisher_id",
            "batch_fraud_probability", "batch_is_flagged", "is_fraud",
        ])
        self.assertTrue(campaign_fraud_rates(empty).empty)
        self.assertTrue(publisher_fraud_rates(empty).empty)


if __name__ == "__main__":
    unittest.main()
