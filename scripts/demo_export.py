#!/usr/bin/env python
"""Phase 9 demo export — produces a self-contained demo_bundle/ directory.

The bundle can be shared as a portfolio artifact and will also serve as the
data source for Project 2's SwiftUI on-device fraud-triage app.

Usage
-----
    python scripts/demo_export.py [--output-dir PATH]

Outputs
-------
    demo_bundle/
        demo_summary.json          — all key metrics in one file
        reconciliation_charts.png  — Phase 6 chart bundle (copied)
        reconciled_clicks_sample.csv — first 200 rows of reconciled output
        DEMO_README.md             — shareable one-page narrative
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Paths (relative to project root)
# ---------------------------------------------------------------------------

RECON_OUTPUT = ROOT / "reconciliation" / "output"
BATCH_PARQUET = ROOT / "data" / "batch" / "batch_scored_clicks.parquet"
TRAINING_METRICS = ROOT / "models" / "training_metrics.json"
BATCH_TRAINING_METRICS = ROOT / "models" / "batch_training_metrics.json"
CAMPAIGN_STATS = ROOT / "models" / "campaign_stats.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict:
    with path.open() as fh:
        return json.load(fh)


def _top_n_by(df: pd.DataFrame, group_col: str, n: int = 5) -> list[dict]:
    """Return top-N groups by flag rate as list-of-dicts for JSON export."""
    agg = (
        df.groupby(group_col)
        .agg(
            total_clicks=(group_col, "count"),
            flagged=("batch_is_flagged", "sum"),
            confirmed_fraud=("is_fraud", "sum"),
        )
        .reset_index()
    )
    agg["flag_rate"] = agg["flagged"] / agg["total_clicks"].clip(lower=1)
    top = agg.sort_values("flag_rate", ascending=False).head(n)
    return top.rename(columns={group_col: "id"}).to_dict(orient="records")


def _fmt_pct(v: float) -> str:
    return f"{v:.2%}"


# ---------------------------------------------------------------------------
# Build the summary JSON
# ---------------------------------------------------------------------------

def build_summary(recon_metrics: dict, training: dict, batch_training: dict,
                  batch_df: pd.DataFrame) -> dict:
    speed = recon_metrics["speed"]
    batch = recon_metrics["batch"]
    latency = recon_metrics.get("latency_ms", {})
    drift = recon_metrics.get("drift_by_replay_window", [])

    recall_gap_window1 = (
        drift[0]["batch"]["recall"] - drift[0]["speed"]["recall"] if drift else None
    )

    top_campaigns = _top_n_by(batch_df, "campaign_id", n=5) if not batch_df.empty else []
    top_publishers = _top_n_by(batch_df, "publisher_id", n=5) if not batch_df.empty else []

    return {
        "project": "Ad-Click Fraud Detection — Lambda Architecture",
        "dataset": "TalkingData AdTracking (1 M click sample)",
        "pipeline": {
            "kafka_topics": ["clicks", "click_alerts"],
            "speed_layer": "PyFlink stateful stream scoring (XGBoost)",
            "batch_layer": "Apache Spark retraining + Delta Lake / Hive",
            "reconciliation": "Speed vs batch join on click_id; delayed is_fraud labels",
        },
        "model_performance": {
            "speed_layer": {
                "model": "XGBoost (speed model)",
                "roc_auc": training["xgboost_primary"]["roc_auc"],
                "pr_auc": training["xgboost_primary"]["pr_auc"],
                "flag_threshold": training["xgboost_primary"]["flag_threshold"],
                "train_rows": training["time_split"]["train_rows"],
                "test_rows": training["time_split"]["test_rows"],
                "features": training["feature_order"],
            },
            "batch_layer": {
                "model": "XGBoost (batch retrained)",
                "roc_auc": batch_training["roc_auc"],
                "pr_auc": batch_training["pr_auc"],
                "flag_threshold": batch_training["flag_threshold"],
                "rows": batch_training["rows"],
            },
            "baseline_logistic_regression": {
                "roc_auc": training["logistic_regression"]["roc_auc"],
                "pr_auc": training["logistic_regression"]["pr_auc"],
            },
        },
        "reconciliation": {
            "matched_clicks": recon_metrics["matched_clicks"],
            "layer_agreement_rate": recon_metrics["agreement_rate"],
            "agreement_rate_pct": _fmt_pct(recon_metrics["agreement_rate"]),
            "speed_pr_auc": speed["pr_auc"],
            "batch_pr_auc": batch["pr_auc"],
            "speed_precision": speed["precision"],
            "batch_precision": batch["precision"],
            "speed_recall": speed["recall"],
            "batch_recall": batch["recall"],
        },
        "drift": {
            "replay_windows": len(drift),
            "recall_gap_window1_batch_minus_speed": recall_gap_window1,
            "recall_gap_window1_pct": _fmt_pct(recall_gap_window1) if recall_gap_window1 is not None else None,
            "note": (
                "Window 1 gap quantifies the cost of not yet having retraining data: "
                "batch layer catches this many more fraud clicks in the earliest replay slice."
            ),
        },
        "latency_ms": latency,
        "campaign_intelligence": {
            "total_campaigns": int(batch_df["campaign_id"].nunique()) if not batch_df.empty else None,
            "top_5_flagged_campaigns": top_campaigns,
        },
        "publisher_intelligence": {
            "total_publishers": int(batch_df["publisher_id"].nunique()) if not batch_df.empty else None,
            "top_5_flagged_publishers": top_publishers,
        },
        "incremental_retraining_experiment": training.get("incremental_experiment", {}),
    }


# ---------------------------------------------------------------------------
# DEMO_README.md content
# ---------------------------------------------------------------------------

DEMO_README = """\
# Ad-Click Fraud Detection — Demo Bundle

This bundle is a self-contained export from a Lambda-architecture click-fraud
detection system built with Kafka, PyFlink, Apache Spark, Delta Lake, and XGBoost.

## What this system does

1. **Speed layer (PyFlink)** — consumes a live Kafka stream of JSON click events,
   computes 11 incremental ad-fraud features per IP in real time (velocity windows,
   fingerprint entropy, click-to-install delta, campaign/publisher conversion rates),
   scores each click with an XGBoost model, and publishes high-risk clicks to a
   `click_alerts` Kafka topic — all within ~2s for the uncontested p50.

2. **Batch layer (Spark)** — periodically reprocesses the full click history once
   delayed attribution labels arrive (real ad-fraud labels come hours-to-days after
   the click), retrains XGBoost on the enriched dataset, and writes curated results
   to Delta Lake (queryable via Hive).

3. **Reconciliation** — speed-layer and batch-layer predictions for the same clicks
   are joined and compared to measure how much the real-time approximation drifts
   from the batch "ground truth" before the next retraining cycle.

## Why Lambda fits click-fraud

| Layer  | What it catches | Latency | Label requirement |
|--------|-----------------|---------|-------------------|
| Speed  | Bot patterns visible in click velocity, fingerprint entropy, uniform timing | ~2s p50 | None — heuristic features only |
| Batch  | Sophisticated farms, zero-conversion-rate publishers, near-zero attribution | Hours–days | Delayed attribution/conversion label |

The speed layer blocks cheap bot clicks before ad spend is charged. The batch layer
corrects for patterns the speed layer's pre-trained model misses, and retraining
closes the accuracy gap on the next cycle.

## Key results

| Metric | Value |
|--------|-------|
| Speed model ROC-AUC | **0.9954** |
| Speed model PR-AUC | **0.9056** |
| Batch model ROC-AUC | **0.9956** |
| Batch model PR-AUC | **0.9159** |
| Layer agreement rate | **97.7%** |
| Recall gap (window 1, batch − speed) | **+15.8 pp** |
| p50 scoring latency | **~1,911 ms** |
| p99 scoring latency | **~3,261 ms** |

The +15.8 pp recall gap in replay window 1 is the headline drift number: before
the first retraining cycle, the batch layer catches 15.8 percentage points more
fraud clicks than the speed layer's pre-trained model. Retraining closes this gap.

## Bundle contents

| File | Description |
|------|-------------|
| `demo_summary.json` | All metrics, top flagged campaigns/publishers, model metadata |
| `reconciliation_charts.png` | Score distributions, PR curves, drift, alerts vs confirmations |
| `reconciled_clicks_sample.csv` | 200-row joined speed + batch output sample |
| `DEMO_README.md` | This document |

## Feeding Project 2 (SwiftUI / CoreML app)

`reconciled_clicks_sample.csv` and `demo_summary.json` are designed to be the
static data source for the on-device fraud-triage SwiftUI app. The CSV contains
`click_id`, `speed_probability`, `batch_probability`, and `true_label` — the
fields needed to display the fraud score, risk band, and ground-truth label for
each click in the app's list/detail view.

## Privacy note

Inference in the SwiftUI app runs fully on-device via CoreML — no click data
leaves the device for prediction. This mirrors the on-device processing design
mandated by Apple's SKAdNetwork / AdAttributionKit privacy model: raw click
signals are never exposed to a remote scoring endpoint.
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 9 demo bundle export")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "demo_bundle",
                        help="Destination directory (default: demo_bundle/)")
    parser.add_argument("--sample-rows", type=int, default=200,
                        help="Number of rows in the reconciled clicks sample CSV")
    args = parser.parse_args()

    out: Path = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    # ── Load source data ────────────────────────────────────────────────────
    print("Loading reconciliation metrics …")
    if not (RECON_OUTPUT / "reconciliation_metrics.json").exists():
        raise SystemExit(
            "ERROR: reconciliation_metrics.json not found. "
            "Run: python reconciliation/reconcile.py"
        )
    recon_metrics = _load_json(RECON_OUTPUT / "reconciliation_metrics.json")
    training = _load_json(TRAINING_METRICS)
    batch_training = _load_json(BATCH_TRAINING_METRICS)

    print("Loading batch parquet (campaign/publisher columns) …")
    if BATCH_PARQUET.exists():
        batch_df = pd.read_parquet(BATCH_PARQUET, columns=[
            "click_id", "campaign_id", "publisher_id",
            "batch_fraud_probability", "batch_is_flagged", "is_fraud",
        ])
    else:
        print(f"  WARNING: {BATCH_PARQUET} not found — campaign/publisher data omitted.")
        batch_df = pd.DataFrame()

    # ── Build and write demo_summary.json ───────────────────────────────────
    print("Building demo_summary.json …")
    summary = build_summary(recon_metrics, training, batch_training, batch_df)
    summary_path = out / "demo_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"  → {summary_path}")

    # ── Copy reconciliation chart bundle ────────────────────────────────────
    chart_src = RECON_OUTPUT / "reconciliation_charts.png"
    if chart_src.exists():
        shutil.copy2(chart_src, out / "reconciliation_charts.png")
        print(f"  → {out / 'reconciliation_charts.png'}")
    else:
        print(f"  WARNING: {chart_src} not found — skipping chart copy.")

    # ── Write reconciled clicks sample ──────────────────────────────────────
    clicks_src = RECON_OUTPUT / "reconciled_clicks.csv"
    if clicks_src.exists():
        sample = pd.read_csv(clicks_src).head(args.sample_rows)
        sample_path = out / "reconciled_clicks_sample.csv"
        sample.to_csv(sample_path, index=False)
        print(f"  → {sample_path} ({len(sample)} rows)")
    else:
        print(f"  WARNING: {clicks_src} not found — skipping sample CSV.")

    # ── Write DEMO_README.md ────────────────────────────────────────────────
    readme_path = out / "DEMO_README.md"
    readme_path.write_text(DEMO_README)
    print(f"  → {readme_path}")

    print(f"\n✅  Demo bundle written to: {out}/")
    print("    Contents:")
    for f in sorted(out.iterdir()):
        size_kb = f.stat().st_size / 1024
        print(f"      {f.name:<40} {size_kb:>7.1f} KB")


if __name__ == "__main__":
    main()
