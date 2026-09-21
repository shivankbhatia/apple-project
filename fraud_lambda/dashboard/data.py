"""Data access layer for the Phase 8 Click Fraud monitoring dashboard."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


# ---------------------------------------------------------------------------
# Phase 6 reconciliation outputs
# ---------------------------------------------------------------------------

def load_report(metrics_path: Path) -> dict[str, Any] | None:
    """Load the Phase 6 reconciliation report; returns None before it has run."""
    if not metrics_path.exists():
        return None
    with metrics_path.open() as fh:
        return json.load(fh)


def load_clicks(clicks_path: Path) -> pd.DataFrame:
    """Load the Phase 6 joined output and normalize timestamp columns."""
    if not clicks_path.exists():
        return pd.DataFrame()
    clicks = pd.read_csv(clicks_path)
    for col in ("click_time", "scored_at"):
        if col in clicks:
            clicks[col] = pd.to_datetime(clicks[col], utc=True, errors="coerce")
    return clicks


def alerts(clicks: pd.DataFrame, limit: int = 100) -> pd.DataFrame:
    """Return newest speed-layer alerts in a compact monitoring-friendly form."""
    if clicks.empty or "speed_flagged" not in clicks:
        return pd.DataFrame()
    out = clicks[clicks["speed_flagged"].fillna(0).astype(int) == 1].copy()
    time_col = "click_time" if "click_time" in out else None
    if time_col:
        out = out.sort_values(time_col, ascending=False)
    cols = [c for c in ("click_id", "click_time", "speed_probability",
                        "batch_probability", "true_label", "latency_ms")
            if c in out]
    return out.loc[:, cols].head(limit)


# ---------------------------------------------------------------------------
# Phase 5 batch-scored output (full parquet with campaign / publisher columns)
# ---------------------------------------------------------------------------

def load_batch_scored(path: Path) -> pd.DataFrame:
    """Load the Phase 5 batch-scored parquet that carries campaign / publisher columns."""
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path, columns=[
        "click_id", "campaign_id", "publisher_id",
        "batch_fraud_probability", "batch_is_flagged", "is_fraud",
    ])
    df["batch_is_flagged"] = df["batch_is_flagged"].fillna(0).astype(int)
    df["is_fraud"] = df["is_fraud"].fillna(0).astype(int)
    return df


def _fraud_rates(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """Aggregate per-group fraud rate, click volume, and flag count."""
    agg = df.groupby(group_col).agg(
        total_clicks=(group_col, "count"),
        flagged=("batch_is_flagged", "sum"),
        confirmed_fraud=("is_fraud", "sum"),
        mean_score=("batch_fraud_probability", "mean"),
    ).reset_index()
    agg["fraud_rate"] = agg["confirmed_fraud"] / agg["total_clicks"].clip(lower=1)
    agg["flag_rate"] = agg["flagged"] / agg["total_clicks"].clip(lower=1)
    return agg.sort_values("flag_rate", ascending=False)


def campaign_fraud_rates(df: pd.DataFrame) -> pd.DataFrame:
    """Return per-campaign fraud/flag rate stats sorted by flag rate descending."""
    return _fraud_rates(df, "campaign_id")


def publisher_fraud_rates(df: pd.DataFrame) -> pd.DataFrame:
    """Return per-publisher fraud/flag rate stats sorted by flag rate descending."""
    return _fraud_rates(df, "publisher_id")
