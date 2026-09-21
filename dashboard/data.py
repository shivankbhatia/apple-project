"""Small, dependency-light data access layer for the Phase 7 dashboard."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def load_report(metrics_path: Path) -> dict[str, Any] | None:
    """Load the Phase 6 report, returning None before reconciliation has run."""
    if not metrics_path.exists():
        return None
    with metrics_path.open() as source:
        return json.load(source)


def load_clicks(clicks_path: Path) -> pd.DataFrame:
    """Load the Phase 6 joined output and normalize dashboard fields."""
    if not clicks_path.exists():
        return pd.DataFrame()
    clicks = pd.read_csv(clicks_path)
    for column in ("click_time", "scored_at"):
        if column in clicks:
            clicks[column] = pd.to_datetime(clicks[column], utc=True, errors="coerce")
    return clicks


def alerts(clicks: pd.DataFrame, limit: int = 100) -> pd.DataFrame:
    """Return newest speed-layer alerts in a compact monitoring-friendly form."""
    if clicks.empty or "speed_flagged" not in clicks:
        return pd.DataFrame()
    output = clicks[clicks["speed_flagged"].fillna(0).astype(int) == 1].copy()
    time_column = "click_time" if "click_time" in output else None
    if time_column:
        output = output.sort_values(time_column, ascending=False)
    columns = [column for column in ("click_id", "click_time", "speed_probability", "batch_probability", "true_label", "latency_ms") if column in output]
    return output.loc[:, columns].head(limit)
