from __future__ import annotations

import unittest

from producer.click_schema import validate_click
from producer.kafka_producer import normalize_click, synthetic_farm_events


class ClickProducerTests(unittest.TestCase):
    def test_raw_talkingdata_row_maps_to_valid_click_contract(self) -> None:
        record = normalize_click({"ip": "42", "app": "3", "device": "1", "os": "13", "channel": "9",
                                  "click_time": "2017-11-06 10:00:00", "attributed_time": "", "is_attributed": "0"})
        self.assertEqual(validate_click(record), [])
        self.assertEqual(record["ip"], "42")
        self.assertEqual(record["campaign_id"], "9")

    def test_farm_events_are_labeled_and_reuse_fingerprints(self) -> None:
        anchor = normalize_click({"ip": "42", "app": "3", "device": "1", "os": "13", "channel": "9",
                                  "click_time": "2017-11-06 10:00:00", "attributed_time": "", "is_attributed": "0"})
        events = list(synthetic_farm_events(anchor, count=4, gap_seconds=1))
        self.assertTrue(all(event["is_synthetic"] == 1 and event["is_fraud"] == 1 for event in events))
        self.assertLess(len({event["device_id"] for event in events}), len(events))
        self.assertTrue(all(not validate_click(event) for event in events))


if __name__ == "__main__":
    unittest.main()
