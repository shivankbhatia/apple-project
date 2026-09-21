from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))
from data import alerts, load_clicks, load_report


class DashboardDataTests(unittest.TestCase):
    def test_missing_outputs_have_safe_empty_state(self) -> None:
        missing = Path("/tmp/does-not-exist-phase-7")
        self.assertIsNone(load_report(missing))
        self.assertTrue(load_clicks(missing).empty)

    def test_loads_and_sorts_alerts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            metrics = root / "metrics.json"
            metrics.write_text(json.dumps({"matched_clicks": 2}))
            clicks = root / "clicks.csv"
            pd.DataFrame({"click_id": ["old", "new"], "speed_flagged": [1, 1], "click_time": ["2017-01-01", "2017-01-02"], "speed_probability": [.8, .9]}).to_csv(clicks, index=False)
            self.assertEqual(load_report(metrics)["matched_clicks"], 2)
            self.assertEqual(alerts(load_clicks(clicks), 1).iloc[0]["click_id"], "new")


if __name__ == "__main__":
    unittest.main()
