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
