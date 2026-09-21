"""Print reproducible Phase 1 findings without requiring a notebook runtime."""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path


def rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def top_rates(counts: Counter[str], positives: Counter[str], limit: int = 5) -> list[dict[str, float | int | str]]:
    return [
        {"id": key, "clicks": counts[key], "fraud_rate": round(rate(positives[key], counts[key]), 6)}
        for key in sorted(counts, key=lambda item: (rate(positives[item], counts[item]), counts[item]), reverse=True)
        if counts[key] >= 100
    ][:limit]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("data/clicks_sample.csv"))
    args = parser.parse_args()

    total = fraud = attributed = 0
    campaign_clicks: Counter[str] = Counter()
    campaign_fraud: Counter[str] = Counter()
    publisher_clicks: Counter[str] = Counter()
    publisher_fraud: Counter[str] = Counter()
    ip_clicks: Counter[str] = Counter()
    ip_attributed: Counter[str] = Counter()
    hour_clicks: Counter[str] = Counter()
    first_time = last_time = None

    with args.input.open(newline="") as source:
        for row in csv.DictReader(source):
            total += 1
            fraud += int(row["is_fraud"])
            attributed += int(row["is_attributed"])
            campaign = row["campaign_id"]
            publisher = row["publisher_id"]
            campaign_clicks[campaign] += 1
            publisher_clicks[publisher] += 1
            campaign_fraud[campaign] += int(row["is_fraud"])
            publisher_fraud[publisher] += int(row["is_fraud"])
            ip_clicks[row["ip"]] += 1
            ip_attributed[row["ip"]] += int(row["is_attributed"])
            hour_clicks[row["click_time"][:13]] += 1
            first_time = first_time or row["click_time"]
            last_time = row["click_time"]

    busiest_ips = [
        {
            "ip": ip,
            "clicks": ip_clicks[ip],
            "attribution_rate": round(rate(ip_attributed[ip], ip_clicks[ip]), 6),
        }
        for ip, _ in ip_clicks.most_common(5)
    ]
    print("Phase 1 EDA summary")
    print(f"window: {first_time} to {last_time}")
    print(f"clicks: {total:,}")
    print(f"bootstrap fraud: {fraud:,} ({rate(fraud, total):.4%})")
    print(f"attributed installs: {attributed:,} ({rate(attributed, total):.4%})")
    print(f"unique IPs: {len(ip_clicks):,}")
    print(f"busiest hour: {hour_clicks.most_common(1)[0]}")
    print(f"top campaign fraud rates (minimum 100 clicks): {top_rates(campaign_clicks, campaign_fraud)}")
    print(f"top publisher fraud rates (minimum 100 clicks): {top_rates(publisher_clicks, publisher_fraud)}")
    print(f"highest-volume IPs and attribution rates: {busiest_ips}")


if __name__ == "__main__":
    main()
