"""Create a reproducible, contiguous TalkingData click sample for Phase 1.

The competition's source file is already chronological.  This program refuses
to silently use an out-of-order selected window and can additionally validate
the full source in a streaming pass without loading the 7 GB CSV in memory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterator


INPUT_COLUMNS = {
    "ip", "app", "device", "os", "channel", "click_time",
    "attributed_time", "is_attributed",
}
OUTPUT_COLUMNS = [
    "click_id", "ad_id", "campaign_id", "publisher_id", "device_id",
    "ip", "os", "timestamp", "click_time", "attributed_time",
    "is_attributed", "click_to_install_delta", "is_synthetic", "is_fraud",
]
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def click_id(row: dict[str, str]) -> str:
    """Stable ID shared by replay, Flink, Delta, and Hive."""
    natural_key = "|".join(
        row[name] for name in ("ip", "device", "os", "app", "channel", "click_time")
    )
    return hashlib.blake2b(natural_key.encode("utf-8"), digest_size=16).hexdigest()


def install_delta_seconds(click_time: str, attributed_time: str) -> str:
    if not attributed_time:
        return ""
    start = datetime.strptime(click_time, TIME_FORMAT)
    end = datetime.strptime(attributed_time, TIME_FORMAT)
    return str(int((end - start).total_seconds()))


def mapped_row(row: dict[str, str]) -> dict[str, str]:
    return {
        "click_id": click_id(row),
        "ad_id": row["app"],
        "campaign_id": row["channel"],
        # TalkingData exposes channel only; it is a documented publisher proxy.
        "publisher_id": row["channel"],
        "device_id": row["device"],
        "ip": row["ip"],
        "os": row["os"],
        "timestamp": row["click_time"],
        "click_time": row["click_time"],
        "attributed_time": row["attributed_time"],
        "is_attributed": row["is_attributed"],
        "click_to_install_delta": install_delta_seconds(row["click_time"], row["attributed_time"]),
        "is_synthetic": "0",
        "is_fraud": "0",  # assigned after IP-window aggregates are known
    }


def percentile(values: list[int], percentile_value: float) -> int:
    ordered = sorted(values)
    index = max(0, math.ceil(percentile_value * len(ordered)) - 1)
    return ordered[index]


def stream_rows(path: Path) -> Iterator[dict[str, str]]:
    with path.open(newline="") as source:
        reader = csv.DictReader(source)
        missing = INPUT_COLUMNS.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Source is missing expected TalkingData columns: {sorted(missing)}")
        yield from reader


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    parser.add_argument("--rows", type=int, default=1_000_000)
    parser.add_argument("--start-row", type=int, default=0,
                        help="Zero-based source row at which the contiguous sample begins.")
    parser.add_argument("--validate-full-order", action="store_true",
                        help="Stream the whole source and fail if click_time ever decreases.")
    parser.add_argument("--velocity-percentile", type=float, default=0.999)
    parser.add_argument("--max-attribution-rate", type=float, default=0.001)
    args = parser.parse_args()

    if args.rows < 1 or args.start_row < 0:
        raise ValueError("--rows must be positive and --start-row cannot be negative")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    unlabeled_path = args.output_dir / "clicks_sample_unlabeled.csv"
    selected_previous_time: str | None = None
    full_previous_time: str | None = None
    selected = 0
    total = 0

    with unlabeled_path.open("w", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for source_row in stream_rows(args.input):
            current_time = source_row["click_time"]
            if args.validate_full_order and full_previous_time and current_time < full_previous_time:
                raise ValueError(
                    f"Source is not time ordered at source row {total}: "
                    f"{current_time} follows {full_previous_time}"
                )
            full_previous_time = current_time
            if args.start_row <= total < args.start_row + args.rows:
                if selected_previous_time and current_time < selected_previous_time:
                    raise ValueError("Selected window is not time ordered")
                writer.writerow(mapped_row(source_row))
                selected_previous_time = current_time
                selected += 1
            total += 1
            if selected == args.rows and not args.validate_full_order:
                break

    if selected != args.rows:
        raise ValueError(f"Requested {args.rows} rows but source only yielded {selected} from start row {args.start_row}")

    per_ip_clicks: Counter[str] = Counter()
    per_ip_attributions: Counter[str] = Counter()
    with unlabeled_path.open(newline="") as sample:
        for row in csv.DictReader(sample):
            per_ip_clicks[row["ip"]] += 1
            per_ip_attributions[row["ip"]] += int(row["is_attributed"])

    velocity_cutoff = percentile(list(per_ip_clicks.values()), args.velocity_percentile)
    fraud_ips = {
        ip for ip, count in per_ip_clicks.items()
        if count >= velocity_cutoff
        and per_ip_attributions[ip] / count <= args.max_attribution_rate
    }

    final_path = args.output_dir / "clicks_sample.csv"
    tiny_path = args.output_dir / "clicks_sample_1k.csv"
    fraud_count = 0
    with unlabeled_path.open(newline="") as sample, final_path.open("w", newline="") as final, tiny_path.open("w", newline="") as tiny:
        reader = csv.DictReader(sample)
        final_writer = csv.DictWriter(final, fieldnames=OUTPUT_COLUMNS)
        tiny_writer = csv.DictWriter(tiny, fieldnames=OUTPUT_COLUMNS)
        final_writer.writeheader()
        tiny_writer.writeheader()
        for index, row in enumerate(reader):
            row["is_fraud"] = str(int(row["ip"] in fraud_ips))
            fraud_count += int(row["is_fraud"])
            final_writer.writerow(row)
            if index < 1_000:
                tiny_writer.writerow(row)

    unlabeled_path.unlink()
    metadata = {
        "source": str(args.input),
        "source_rows_scanned": total,
        "sample_start_row": args.start_row,
        "sample_rows": selected,
        "click_time_start": None,
        "click_time_end": None,
        "source_order_validated": args.validate_full_order,
        "label_definition": {
            "positive": "IP is in the sample-window velocity tail and has near-zero attribution rate; this is a bootstrap heuristic, not ground truth.",
            "velocity_percentile": args.velocity_percentile,
            "velocity_count_cutoff": velocity_cutoff,
            "max_attribution_rate": args.max_attribution_rate,
            "flagged_ips": len(fraud_ips),
        },
        "is_fraud_positive_rows": fraud_count,
        "is_fraud_rate": fraud_count / selected,
    }
    with final_path.open(newline="") as final:
        reader = csv.DictReader(final)
        first = next(reader)
        metadata["click_time_start"] = first["click_time"]
        for row in reader:
            metadata["click_time_end"] = row["click_time"]
        if metadata["click_time_end"] is None:
            metadata["click_time_end"] = first["click_time"]
    (args.output_dir / "clicks_sample_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
