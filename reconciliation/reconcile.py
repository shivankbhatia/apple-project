"""Phase 6 reconciliation for ad-click speed and batch predictions."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, precision_recall_curve, precision_score, recall_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "output"


def read_json_directory(path: Path) -> pd.DataFrame:
    """Read only finalized Flink newline-delimited JSON files."""
    files = sorted(p for p in path.rglob("*.json") if not p.name.startswith("."))
    if not files:
        raise FileNotFoundError(f"No committed JSON files below {path}")
    return pd.concat([pd.read_json(p, lines=True) for p in files], ignore_index=True)


def read_file(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".json", ".jsonl"}:
        return pd.read_json(path, lines=True)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    raise ValueError("Batch input must be CSV, JSONL, or Parquet")


def load_spark(delta_path: Path, batch_table: str, hive_uri: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Canonical deployment path: Delta speed output + Phase 5 Hive table."""
    from delta import configure_spark_with_delta_pip
    from pyspark.sql import SparkSession
    builder = (SparkSession.builder.appName("ClickReconciliation")
               .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
               .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
               .config("spark.hadoop.hive.metastore.uris", hive_uri).enableHiveSupport())
    spark = configure_spark_with_delta_pip(builder).getOrCreate()
    try:
        speed = spark.read.format("delta").load(str(delta_path)).toPandas()
        try:
            batch = spark.table(batch_table).toPandas()
        except Exception as error:
            portable = ROOT / "data" / "batch" / "batch_scored_clicks.parquet"
            if not portable.exists():
                raise RuntimeError(
                    f"Hive table {batch_table} is unavailable and no portable batch view exists at {portable}. "
                    "Run: python spark-batch/batch_retrain.py --skip-hive"
                ) from error
            print(f"Hive table unavailable; using portable batch view: {portable}")
            batch = spark.read.parquet(str(portable)).toPandas()
        return speed, batch
    finally:
        spark.stop()


def _required(frame: pd.DataFrame, names: list[str], label: str) -> str:
    found = next((name for name in names if name in frame.columns), None)
    if not found:
        raise ValueError(f"Missing {label}; expected one of {names}")
    return found


def canonicalize(speed: pd.DataFrame, batch: pd.DataFrame) -> pd.DataFrame:
    """Join two phase outputs on the immutable click_id data-contract key."""
    ss = _required(speed, ["fraud_probability", "speed_probability"], "speed score")
    bs = _required(batch, ["batch_fraud_probability", "batch_probability", "fraud_probability"], "batch score")
    label_source = batch if any(c in batch for c in ("is_fraud", "isFraud", "true_label")) else speed
    label = _required(label_source, ["is_fraud", "isFraud", "true_label"], "delayed label")
    s = pd.DataFrame({
        "click_id": speed[_required(speed, ["click_id"], "speed click id")].astype(str),
        "speed_probability": pd.to_numeric(speed[ss], errors="coerce"),
        "speed_flagged": pd.to_numeric(speed.get("is_flagged", speed[ss] >= .5), errors="coerce"),
        "latency_ms": pd.to_numeric(speed.get("latency_ms", np.nan), errors="coerce"),
        "click_time": speed.get("click_time", speed.get("timestamp", pd.NaT)),
    }).drop_duplicates("click_id", keep="last")
    b = pd.DataFrame({
        "click_id": batch[_required(batch, ["click_id"], "batch click id")].astype(str),
        "batch_probability": pd.to_numeric(batch[bs], errors="coerce"),
        "batch_flagged": pd.to_numeric(batch.get("batch_is_flagged", batch[bs] >= .5), errors="coerce"),
        "true_label": pd.to_numeric(label_source[label], errors="coerce"),
    }).drop_duplicates("click_id", keep="last")
    joined = s.merge(b, on="click_id").dropna(subset=["speed_probability", "batch_probability", "true_label"])
    if joined.empty:
        raise ValueError("No matching click_id values between speed and batch inputs")
    for column in ("true_label", "speed_flagged", "batch_flagged"):
        joined[column] = joined[column].fillna(0).astype(int)
    joined["click_time"] = pd.to_datetime(joined.click_time, utc=True, errors="coerce")
    return joined


def metrics(y: pd.Series, scores: pd.Series, flags: pd.Series) -> dict[str, float | None]:
    result: dict[str, float | None] = {
        "precision": float(precision_score(y, flags, zero_division=0)),
        "recall": float(recall_score(y, flags, zero_division=0)),
    }
    if y.nunique() < 2:
        return result | {"roc_auc": None, "pr_auc": None}
    return result | {"roc_auc": float(roc_auc_score(y, scores)), "pr_auc": float(average_precision_score(y, scores))}


def calculate_report(joined: pd.DataFrame, drift_buckets: int = 8) -> dict[str, Any]:
    if drift_buckets < 2:
        raise ValueError("drift_buckets must be at least 2")
    latency = joined.latency_ms.dropna()
    report: dict[str, Any] = {
        "matched_clicks": len(joined),
        "agreement_rate": float((joined.speed_flagged == joined.batch_flagged).mean()),
        "speed": metrics(joined.true_label, joined.speed_probability, joined.speed_flagged),
        "batch": metrics(joined.true_label, joined.batch_probability, joined.batch_flagged),
        "latency_ms": {} if latency.empty else {p: float(latency.quantile(q)) for p, q in (("p50", .5), ("p95", .95), ("p99", .99))},
    }
    ordered = joined.sort_values("click_time", na_position="last").reset_index(drop=True)
    ordered["window"] = pd.qcut(np.arange(len(ordered)), min(drift_buckets, len(ordered)), labels=False, duplicates="drop")
    drift = []
    for window, part in ordered.groupby("window", observed=True):
        speed, batch = metrics(part.true_label, part.speed_probability, part.speed_flagged), metrics(part.true_label, part.batch_probability, part.batch_flagged)
        drift.append({"window": int(window) + 1, "clicks": len(part), "speed": speed, "batch": batch,
                      "precision_gap_batch_minus_speed": batch["precision"] - speed["precision"],
                      "recall_gap_batch_minus_speed": batch["recall"] - speed["recall"]})
    report["drift_by_replay_window"] = drift
    return report


def charts(joined: pd.DataFrame, report: dict[str, Any], output: Path) -> Path:
    # Keep metric-only/test runs lightweight; matplotlib is only needed when
    # rendering the Phase 6 visual artifact.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    axes[0, 0].hist(joined.speed_probability, bins=35, alpha=.65, label="speed")
    axes[0, 0].hist(joined.batch_probability, bins=35, alpha=.55, label="batch")
    axes[0, 0].set(title="Score distribution", xlabel="Fraud probability"); axes[0, 0].legend()
    if joined.true_label.nunique() > 1:
        for scores, name in ((joined.speed_probability, "speed"), (joined.batch_probability, "batch")):
            precision, recall, _ = precision_recall_curve(joined.true_label, scores); axes[0, 1].plot(recall, precision, label=name)
    axes[0, 1].set(title="Precision–recall", xlabel="Recall", ylabel="Precision", xlim=(0, 1), ylim=(0, 1)); axes[0, 1].legend()
    windows = report["drift_by_replay_window"]
    axes[1, 0].plot([x["window"] for x in windows], [x["speed"]["precision"] for x in windows], marker="o", label="speed")
    axes[1, 0].plot([x["window"] for x in windows], [x["batch"]["precision"] for x in windows], marker="o", label="batch")
    axes[1, 0].set(title="Precision drift across replay", xlabel="Replay window", ylabel="Precision", ylim=(0, 1)); axes[1, 0].legend()
    timeline = joined.dropna(subset=["click_time"]).copy()
    if not timeline.empty:
        timeline["minute"] = timeline.click_time.dt.floor("min")
        counts = timeline.groupby("minute")[["speed_flagged", "true_label"]].sum()
        axes[1, 1].plot(counts.index, counts.speed_flagged, label="alerts fired"); axes[1, 1].plot(counts.index, counts.true_label, label="confirmed fraud")
        axes[1, 1].tick_params(axis="x", rotation=25)
    axes[1, 1].set(title="Alerts vs confirmations", xlabel="Click time"); axes[1, 1].legend()
    fig.tight_layout(); path = output / "reconciliation_charts.png"; fig.savefig(path, dpi=160); plt.close(fig)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 6 click-fraud reconciliation")
    parser.add_argument("--speed-json-dir", type=Path, help="Flink staging JSON directory")
    parser.add_argument("--batch-file", type=Path, help="Phase 5 predictions: CSV, JSONL, or Parquet")
    parser.add_argument("--delta-path", type=Path, default=ROOT / "data/delta/scored_clicks")
    parser.add_argument("--batch-table", default="ad_fraud.batch_scored_clicks")
    parser.add_argument("--hive-uri", default="thrift://localhost:9083")
    parser.add_argument("--output-dir", type=Path, default=OUT); parser.add_argument("--drift-buckets", type=int, default=8)
    args = parser.parse_args()
    if bool(args.speed_json_dir) != bool(args.batch_file): parser.error("Pass both local inputs, or neither for Delta/Hive mode")
    speed, batch = (read_json_directory(args.speed_json_dir), read_file(args.batch_file)) if args.speed_json_dir else load_spark(args.delta_path, args.batch_table, args.hive_uri)
    joined = canonicalize(speed, batch); report = calculate_report(joined, args.drift_buckets)
    args.output_dir.mkdir(parents=True, exist_ok=True); joined.to_csv(args.output_dir / "reconciled_clicks.csv", index=False)
    (args.output_dir / "reconciliation_metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2)); print(f"Wrote {charts(joined, report, args.output_dir)}")


if __name__ == "__main__": main()
