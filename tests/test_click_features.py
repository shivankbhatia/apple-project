from __future__ import annotations

import unittest

from features.click_features import FEATURE_ORDER, IncrementalClickFeatures, enrich_ordered_records, vectorize


def click(click_id: str, timestamp: str, ip: str, device: str, os: str, campaign: str = "7") -> dict[str, str]:
    return {
        "click_id": click_id,
        "timestamp": timestamp,
        "click_time": timestamp,
        "ip": ip,
        "device_id": device,
        "os": os,
        "campaign_id": campaign,
        "publisher_id": campaign,
        "attributed_time": "",
        "click_to_install_delta": "",
    }


class ClickFeatureParityTests(unittest.TestCase):
    def test_incremental_and_batch_entry_points_match(self) -> None:
        rows = [
            click("a", "2017-11-06 10:00:00", "farm", "same-device", "13"),
            click("b", "2017-11-06 10:00:10", "farm", "same-device", "13"),
            click("c", "2017-11-06 10:00:40", "farm", "same-device", "13"),
            click("d", "2017-11-06 10:06:00", "organic", "d-1", "14"),
            click("e", "2017-11-06 10:07:00", "organic", "d-2", "15"),
        ]
        stats = {"7": {"clicks": 100, "attributed": 2}}
        stream_engine = IncrementalClickFeatures(stats, stats)
        streamed = [stream_engine.enrich(row) for row in rows]
        batched = enrich_ordered_records(rows, stats, stats)

        self.assertEqual(
            [{key: row[key] for key in FEATURE_ORDER} for row in streamed],
            [{key: row[key] for key in FEATURE_ORDER} for row in batched],
        )

    def test_farm_signature_has_velocity_and_low_fingerprint_entropy(self) -> None:
        engine = IncrementalClickFeatures()
        first = engine.enrich(click("a", "2017-11-06 10:00:00", "farm", "same-device", "13"))
        engine.enrich(click("b", "2017-11-06 10:00:10", "farm", "same-device", "13"))
        third = engine.enrich(click("c", "2017-11-06 10:00:20", "farm", "same-device", "13"))

        self.assertEqual(first["ip_clicks_1m"], 1)
        self.assertEqual(third["ip_clicks_1m"], 3)
        self.assertEqual(third["ip_inter_click_gap_seconds"], 10.0)
        self.assertEqual(third["ip_fingerprint_entropy_5m"], 0.0)

    def test_vector_order_is_stable_and_null_safe(self) -> None:
        row = {feature: index for index, feature in enumerate(FEATURE_ORDER)}
        self.assertEqual(vectorize(row), [float(index) for index in range(len(FEATURE_ORDER))])
        self.assertEqual(len(vectorize({})), len(FEATURE_ORDER))


if __name__ == "__main__":
    unittest.main()
