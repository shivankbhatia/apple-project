"""Small Kafka data-contract consumer for the ``clicks`` topic."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from kafka import KafkaConsumer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from producer.click_schema import validate_click


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default="clicks")
    parser.add_argument("--bootstrap-servers", default="localhost:9092")
    parser.add_argument("--group-id", default="click-schema-check-v1")
    parser.add_argument("--max-messages", type=int, default=100)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    args = parser.parse_args()
    consumer = KafkaConsumer(args.topic, bootstrap_servers=args.bootstrap_servers, group_id=args.group_id,
                             auto_offset_reset="latest", enable_auto_commit=False, consumer_timeout_ms=1_000,
                             value_deserializer=lambda raw: raw.decode("utf-8"))
    valid = malformed_json = invalid = 0
    started = time.monotonic()
    try:
        while valid + malformed_json + invalid < args.max_messages and time.monotonic() - started < args.timeout_seconds:
            for message in consumer:
                try:
                    record = json.loads(message.value)
                except json.JSONDecodeError:
                    malformed_json += 1
                    print(f"malformed JSON partition={message.partition} offset={message.offset}")
                    continue
                errors = validate_click(record)
                if errors:
                    invalid += 1
                    print(f"invalid partition={message.partition} offset={message.offset}: {'; '.join(errors)}")
                else:
                    valid += 1
                if valid + malformed_json + invalid >= args.max_messages:
                    break
    finally:
        consumer.close()
    elapsed = max(time.monotonic() - started, 1e-9)
    print(json.dumps({"valid": valid, "invalid": invalid, "malformed_json": malformed_json,
                      "messages_per_second": round((valid + invalid + malformed_json) / elapsed, 2)}, indent=2))
    if invalid or malformed_json or not valid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
