"""Phase 5 click-fraud batch retraining and delayed-label scoring.

The job deliberately recomputes the shared feature contract in chronological
order, trains a fresh batch model from delayed labels, and publishes scores for
every click to Hive.  Phase 6 then joins this table to the Delta speed output
on ``click_id``.
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from features.click_features import FEATURE_ORDER, IncrementalClickFeatures, vectorize


def snapshots(rows: pd.DataFrame) -> tuple[dict[str, dict[str, int]], dict[str, dict[str, int]]]:
    campaign: dict[str, Counter[str]] = defaultdict(Counter)
    publisher: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows.itertuples(index=False):
        attributed = int(row.is_attributed)
        for target, value in ((campaign, row.campaign_id), (publisher, row.publisher_id)):
            target[str(value)]["clicks"] += 1
            target[str(value)]["attributed"] += attributed
    return dict(campaign), dict(publisher)


def enrich(rows: pd.DataFrame, campaign: dict[str, dict[str, int]], publisher: dict[str, dict[str, int]]) -> np.ndarray:
    engine = IncrementalClickFeatures(campaign, publisher)
    features = np.empty((len(rows), len(FEATURE_ORDER)), dtype=np.float32)
    for index, row in enumerate(rows.itertuples(index=False)):
        features[index] = vectorize(engine.enrich(row._asdict()))
    return features


def threshold_for_f1(labels: np.ndarray, scores: np.ndarray) -> float:
    precision, recall, thresholds = precision_recall_curve(labels, scores)
    f1 = 2 * precision[:-1] * recall[:-1] / np.maximum(precision[:-1] + recall[:-1], 1e-12)
    return float(thresholds[int(np.argmax(f1))])


def build_model(labels: np.ndarray, estimators: int) -> xgb.XGBClassifier:
    positives = int(labels.sum())
    if positives == 0 or positives == len(labels):
        raise ValueError("Delayed labels must contain both fraud and non-fraud clicks.")
    return xgb.XGBClassifier(
        n_estimators=estimators, max_depth=6, learning_rate=.1, subsample=.9,
        colsample_bytree=.9, scale_pos_weight=(len(labels) - positives) / positives,
        eval_metric="aucpr", random_state=42, n_jobs=4, tree_method="hist",
    )


def hive_session(hive_uri: str, warehouse: Path):
    from pyspark.sql import SparkSession
    return (SparkSession.builder.appName("ClickBatchRetrain")
            .config("spark.hadoop.hive.metastore.uris", hive_uri)
            .config("spark.sql.warehouse.dir", str(warehouse.resolve()))
            .enableHiveSupport().getOrCreate())


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 5 delayed-label click batch retraining")
    parser.add_argument("--input", type=Path, default=ROOT / "data" / "clicks_sample.csv")
    parser.add_argument("--models-dir", type=Path, default=ROOT / "models")
    parser.add_argument("--warehouse", type=Path, default=ROOT / "data" / "hive-warehouse")
    parser.add_argument("--output-path", type=Path, default=ROOT / "data" / "batch" / "batch_scored_clicks.parquet")
    parser.add_argument("--hive-uri", default="thrift://localhost:9083")
    parser.add_argument("--table", default="ad_fraud.batch_scored_clicks")
    parser.add_argument("--skip-hive", action="store_true", help="Write the portable Parquet batch view only.")
    parser.add_argument("--test-fraction", type=float, default=.2)
    parser.add_argument("--n-estimators", type=int, default=120)
    args = parser.parse_args()
    if not 0 < args.test_fraction < .5:
        parser.error("--test-fraction must be between 0 and 0.5")

    raw = pd.read_csv(args.input, dtype=str).fillna("")
    required = {"click_id", "click_time", "is_attributed", "is_fraud", "campaign_id", "publisher_id", "device_id", "ip", "os"}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"Input is missing click fields: {sorted(missing)}")
    raw = raw.sort_values("click_time", kind="stable").reset_index(drop=True)
    labels = pd.to_numeric(raw["is_fraud"], errors="raise").to_numpy(dtype=np.int8)
    split = int(len(raw) * (1 - args.test_fraction))
    campaign, publisher = snapshots(raw.iloc[:split])
    features = enrich(raw, campaign, publisher)
    model = build_model(labels[:split], args.n_estimators)
    model.fit(features[:split], labels[:split])
    test_scores = model.predict_proba(features[split:])[:, 1]
    threshold = threshold_for_f1(labels[split:], test_scores)
    all_scores = model.predict_proba(features)[:, 1]
    metrics = {
        "rows": len(raw), "train_rows": split, "test_rows": len(raw) - split,
        "roc_auc": round(float(roc_auc_score(labels[split:], test_scores)), 6),
        "pr_auc": round(float(average_precision_score(labels[split:], test_scores)), 6),
        "flag_threshold": round(threshold, 6),
        "table": args.table,
    }
    args.models_dir.mkdir(parents=True, exist_ok=True)
    with (args.models_dir / "click_fraud_model_batch.pkl").open("wb") as destination:
        pickle.dump(model, destination)
    (args.models_dir / "batch_training_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")

    scored = raw.copy()
    scored["is_fraud"] = labels
    scored["batch_fraud_probability"] = np.round(all_scores, 6)
    scored["batch_is_flagged"] = (all_scores >= threshold).astype(np.int8)
    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    spark = hive_session(args.hive_uri, args.warehouse)
    spark.sparkContext.setLogLevel("WARN")
    try:
        # Host-readable hand-off for Phase 6 when a Docker Hive metastore
        # cannot resolve the host's local file paths.
        spark.createDataFrame(scored).write.mode("overwrite").parquet(str(args.output_path))
        print(f"Written portable batch view: {args.output_path}")
        if args.skip_hive:
            print(json.dumps(metrics, indent=2))
            return
        schema, _ = args.table.split(".", 1)
        database_location = (args.warehouse / f"{schema}.db").resolve().as_uri()
        spark.sql(f"CREATE DATABASE IF NOT EXISTS {schema} LOCATION '{database_location}'")
        spark.read.parquet(str(args.output_path)).write.mode("overwrite").format("parquet").saveAsTable(args.table)
        spark.table(args.table).select("click_id", "batch_fraud_probability", "batch_is_flagged", "is_fraud").show(5, truncate=False)
    finally:
        spark.stop()
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
