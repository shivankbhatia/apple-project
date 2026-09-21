"""Kafka JSON contract for Phase 4 click events."""

from __future__ import annotations

from typing import Any, Mapping

REQUIRED_CLICK_FIELDS = frozenset({
    "click_id", "ad_id", "campaign_id", "publisher_id", "device_id", "ip",
    "os", "timestamp", "click_time", "is_attributed", "is_synthetic", "event_timestamp",
})


def validate_click(record: Mapping[str, Any]) -> list[str]:
    """Return data-contract violations; an empty list means valid."""
    errors = [f"missing required key: {field}" for field in sorted(REQUIRED_CLICK_FIELDS - record.keys())]
    for field in ("click_id", "ip", "click_time", "event_timestamp"):
        if field in record and record[field] in (None, ""):
            errors.append(f"empty required value: {field}")
    for field in ("is_attributed", "is_synthetic"):
        if field in record:
            try:
                if int(record[field]) not in (0, 1):
                    errors.append(f"{field} must be 0 or 1")
            except (TypeError, ValueError):
                errors.append(f"{field} must be integer-like")
    return errors
