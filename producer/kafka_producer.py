"""Replay time-ordered TalkingData clicks to Kafka, optionally injecting farms."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from kafka import KafkaProducer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from producer.click_schema import validate_click

TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def create_producer(bootstrap_servers: str) -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda value: json.dumps(value, separators=(",", ":")).encode("utf-8"),
        key_serializer=lambda key: str(key).encode("utf-8"), acks="all", retries=3,
    )


def stable_click_id(*parts: str) -> str:
    return hashlib.blake2b("|".join(parts).encode("utf-8"), digest_size=16).hexdigest()


def normalize_click(row: dict[str, str]) -> dict[str, Any]:
    """Accept Phase 1 mapped rows; also map a raw TalkingData row if supplied."""
    click_time = row["click_time"]
    if "click_id" in row:
        event: dict[str, Any] = dict(row)
    else:
        event = {
            "click_id": stable_click_id(row["ip"], row["device"], row["os"], row["app"], row["channel"], click_time),
            "ad_id": row["app"], "campaign_id": row["channel"], "publisher_id": row["channel"],
            "device_id": row["device"], "ip": row["ip"], "os": row["os"],
            "timestamp": click_time, "click_time": click_time,
            "attributed_time": row.get("attributed_time", ""), "is_attributed": row["is_attributed"],
            "click_to_install_delta": "", "is_synthetic": "0",
        }
    event["is_attributed"] = int(event["is_attributed"])
    event["is_synthetic"] = int(event.get("is_synthetic", 0))
    event["event_timestamp"] = datetime.now(timezone.utc).isoformat()
    errors = validate_click(event)
    if errors:
        raise ValueError("; ".join(errors))
    return event


def synthetic_farm_events(anchor: dict[str, Any], count: int, gap_seconds: int) -> Iterator[dict[str, Any]]:
    """Deterministic, labeled farm burst for visible velocity/entropy demos."""
    start = datetime.strptime(anchor["click_time"], TIME_FORMAT)
    for index in range(count):
        click_time = start + timedelta(seconds=index * gap_seconds)
        ip = f"farm-{index % 3:02d}"
        device = "farm-device-00"
        yield {
            "click_id": stable_click_id("synthetic-farm", ip, device, click_time.isoformat()),
            "ad_id": "farm-ad-001", "campaign_id": "farm-campaign-001", "publisher_id": "farm-publisher-001",
            "device_id": device, "ip": ip, "os": "farm-os-1",
            "timestamp": click_time.strftime(TIME_FORMAT), "click_time": click_time.strftime(TIME_FORMAT),
            "attributed_time": "", "is_attributed": 0, "click_to_install_delta": "",
            "is_synthetic": 1, "is_fraud": 1, "event_timestamp": datetime.now(timezone.utc).isoformat(),
        }


def replay_clicks(csv_path: Path, topic: str, bootstrap_servers: str, speed_multiplier: float,
                  limit: int | None, start_ts: str | None, inject_farms: bool,
                  farm_every: int, farm_count: int, farm_gap_seconds: int) -> tuple[int, int]:
    if speed_multiplier <= 0:
        raise ValueError("--speed-multiplier must be positive")
    producer = create_producer(bootstrap_servers)
    sent = farm_sent = 0
    previous_click_time: datetime | None = None
    try:
        with csv_path.open(newline="") as source:
            for row in csv.DictReader(source):
                if start_ts and row["click_time"] < start_ts:
                    continue
                if limit is not None and sent >= limit:
                    break
                event = normalize_click(row)
                current_click_time = datetime.strptime(event["click_time"], TIME_FORMAT)
                if previous_click_time:
                    source_gap = max(0.0, (current_click_time - previous_click_time).total_seconds())
                    time.sleep(min(source_gap / speed_multiplier, 2.0))
                producer.send(topic, key=event["ip"], value=event)
                previous_click_time = current_click_time
                sent += 1
                if inject_farms and sent % farm_every == 0:
                    for farm_event in synthetic_farm_events(event, farm_count, farm_gap_seconds):
                        producer.send(topic, key=farm_event["ip"], value=farm_event)
                        farm_sent += 1
                if sent % 1_000 == 0:
                    print(f"sent {sent:,} organic clicks; {farm_sent:,} synthetic farm clicks", flush=True)
        producer.flush()
    finally:
        producer.close()
    return sent, farm_sent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=Path("data/clicks_sample.csv"))
    parser.add_argument("--topic", default="clicks")
    parser.add_argument("--bootstrap-servers", default="localhost:9092")
    parser.add_argument("--speed-multiplier", type=float, default=3_600.0)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--start-ts", help="Inclusive click_time, e.g. '2017-11-06 16:00:00'.")
    parser.add_argument("--inject-farms", action="store_true")
    parser.add_argument("--farm-every", type=int, default=1_000)
    parser.add_argument("--farm-count", type=int, default=30)
    parser.add_argument("--farm-gap-seconds", type=int, default=1)
    args = parser.parse_args()
    if min(args.farm_every, args.farm_count, args.farm_gap_seconds) < 1:
        parser.error("farm arguments must be positive")
    organic, farm = replay_clicks(args.csv, args.topic, args.bootstrap_servers, args.speed_multiplier,
                                  args.limit, args.start_ts, args.inject_farms, args.farm_every,
                                  args.farm_count, args.farm_gap_seconds)
    print(f"complete: {organic:,} organic clicks, {farm:,} synthetic farm clicks")


if __name__ == "__main__":
    main()
