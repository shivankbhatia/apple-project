"""Deterministic click-fraud features shared by stream and batch layers.

The stream layer calls :class:`IncrementalClickFeatures` once per ordered
event. Batch code must call :func:`enrich_ordered_records` on the same ordered
partition, making feature semantics explicit rather than reimplementing them
inside Flink and Spark independently.
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from math import log2
from typing import Any, Deque, Iterable, Mapping


FEATURE_ORDER = [
    "ip_clicks_1m",
    "ip_clicks_5m",
    "ip_clicks_1h",
    "device_clicks_1m",
    "device_clicks_5m",
    "device_clicks_1h",
    "ip_fingerprint_entropy_5m",
    "ip_inter_click_gap_seconds",
    "click_to_install_delta_seconds",
    "campaign_conversion_rate",
    "publisher_conversion_rate",
]

WINDOW_SECONDS = (60, 300, 3600)


def parse_timestamp(value: Any) -> float:
    """Return epoch seconds for TalkingData or ISO-8601 timestamps."""
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def shannon_entropy(values: Iterable[tuple[str, str]]) -> float:
    counts: dict[tuple[str, str], int] = defaultdict(int)
    total = 0
    for value in values:
        counts[value] += 1
        total += 1
    if total == 0:
        return 0.0
    return -sum((count / total) * log2(count / total) for count in counts.values())


def click_to_install_seconds(record: Mapping[str, Any]) -> float:
    value = record.get("click_to_install_delta")
    if value not in (None, ""):
        return float(value)
    timestamp = record.get("timestamp", record.get("click_time"))
    attributed_time = record.get("attributed_time")
    if not attributed_time or not timestamp:
        return 0.0
    return max(0.0, parse_timestamp(attributed_time) - parse_timestamp(timestamp))


def conversion_rate(snapshot: Mapping[str, Any] | None, identifier: Any) -> float:
    """Read a batch-authoritative campaign/publisher rate snapshot safely."""
    if not snapshot:
        return 0.0
    value = snapshot.get(str(identifier), snapshot.get(identifier, 0.0))
    if isinstance(value, Mapping):
        clicks = float(value.get("clicks", 0))
        return float(value.get("attributed", 0)) / clicks if clicks else 0.0
    return float(value)


class IncrementalClickFeatures:
    """In-memory reference implementation of the processing-time feature state."""

    def __init__(
        self,
        campaign_stats: Mapping[str, Any] | None = None,
        publisher_stats: Mapping[str, Any] | None = None,
    ) -> None:
        self.campaign_stats = campaign_stats or {}
        self.publisher_stats = publisher_stats or {}
        # One queue per window makes each event append/pop amortized O(1).
        # A single 1-hour queue scanned three times per record becomes
        # quadratic for TalkingData's heavily reused device identifiers.
        self.ip_timestamps: dict[str, dict[int, Deque[float]]] = defaultdict(
            lambda: {seconds: deque() for seconds in WINDOW_SECONDS}
        )
        self.device_timestamps: dict[str, dict[int, Deque[float]]] = defaultdict(
            lambda: {seconds: deque() for seconds in WINDOW_SECONDS}
        )
        self.ip_fingerprints: dict[str, Deque[tuple[float, tuple[str, str]]]] = defaultdict(deque)
        self.last_ip_timestamp: dict[str, float] = {}

    @staticmethod
    def _trim_timestamps(values: Deque[float], now: float, seconds: int) -> None:
        cutoff = now - seconds
        while values and values[0] < cutoff:
            values.popleft()

    @staticmethod
    def _trim_fingerprints(values: Deque[tuple[float, tuple[str, str]]], now: float) -> None:
        cutoff = now - 300
        while values and values[0][0] < cutoff:
            values.popleft()

    def enrich(self, record: Mapping[str, Any]) -> dict[str, Any]:
        result = dict(record)
        now = parse_timestamp(
            result.get("feature_timestamp", result.get("timestamp", result.get("click_time")))
        )        
        ip = str(result["ip"])
        device = str(result["device_id"])
        fingerprint = (device, str(result["os"]))

        ip_values = self.ip_timestamps[ip]
        device_values = self.device_timestamps[device]
        fingerprint_values = self.ip_fingerprints[ip]
        self._trim_fingerprints(fingerprint_values, now)

        previous_timestamp = self.last_ip_timestamp.get(ip)
        result["ip_inter_click_gap_seconds"] = (
            max(0.0, now - previous_timestamp) if previous_timestamp is not None else 0.0
        )
        fingerprint_values.append((now, fingerprint))
        self.last_ip_timestamp[ip] = now

        for seconds, suffix in zip(WINDOW_SECONDS, ("1m", "5m", "1h")):
            ip_window = ip_values[seconds]
            device_window = device_values[seconds]
            self._trim_timestamps(ip_window, now, seconds)
            self._trim_timestamps(device_window, now, seconds)
            ip_window.append(now)
            device_window.append(now)
            result[f"ip_clicks_{suffix}"] = len(ip_window)
            result[f"device_clicks_{suffix}"] = len(device_window)
        result["ip_fingerprint_entropy_5m"] = shannon_entropy(
            fingerprint for _, fingerprint in fingerprint_values
        )
        result["click_to_install_delta_seconds"] = click_to_install_seconds(result)
        result["campaign_conversion_rate"] = conversion_rate(
            self.campaign_stats, result.get("campaign_id")
        )
        result["publisher_conversion_rate"] = conversion_rate(
            self.publisher_stats, result.get("publisher_id")
        )
        return result


def enrich_ordered_records(
    records: Iterable[Mapping[str, Any]],
    campaign_stats: Mapping[str, Any] | None = None,
    publisher_stats: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Batch entry point: records must be ordered by timestamp within a key."""
    engine = IncrementalClickFeatures(campaign_stats, publisher_stats)
    return [engine.enrich(record) for record in records]


def vectorize(record: Mapping[str, Any]) -> list[float]:
    """Model vector in the exact persisted ``FEATURE_ORDER`` order."""
    return [float(record.get(feature) or 0.0) for feature in FEATURE_ORDER]
