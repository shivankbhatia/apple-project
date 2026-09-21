from __future__ import annotations
import sys
import unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reconciliation"))
from reconcile import calculate_report, canonicalize

class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.speed = pd.DataFrame({"click_id":["a","b","c","extra"], "fraud_probability":[.9,.1,.8,.4], "is_flagged":[1,0,1,0], "latency_ms":[10,20,30,40], "click_time":["2017-11-06 10:00:00","2017-11-06 10:01:00","2017-11-06 10:02:00","2017-11-06 10:03:00"]})
        self.batch = pd.DataFrame({"click_id":["a","b","c"], "batch_fraud_probability":[.95,.2,.3], "batch_is_flagged":[1,0,0], "is_fraud":[1,0,1]})
    def test_join_and_report(self):
        report = calculate_report(canonicalize(self.speed, self.batch), 2)
        self.assertEqual(report["matched_clicks"], 3); self.assertAlmostEqual(report["agreement_rate"], 2 / 3); self.assertEqual(len(report["drift_by_replay_window"]), 2)
    def test_single_class_is_safe(self):
        report = calculate_report(canonicalize(self.speed.iloc[:1], self.batch.iloc[:1]), 2)
        self.assertIsNone(report["speed"]["roc_auc"])

if __name__ == "__main__": unittest.main()
