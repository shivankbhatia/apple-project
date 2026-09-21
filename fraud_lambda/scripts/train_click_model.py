"""Train Phase 3 time-ordered ad-click fraud models and persist speed artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import pickle
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import xgboost as xgb
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score

# Permit direct execution from the repository root as documented in the README.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from features.click_features import FEATURE_ORDER, IncrementalClickFeatures, vectorize


def count_rows(path: Path) -> int:
    with path.open(newline="") as source:
        return sum(1 for _ in csv.DictReader(source))


def conversion_snapshots(path: Path, train_rows: int) -> tuple[dict[str, dict[str, int]], dict[str, dict[str, int]]]:
    campaign: dict[str, Counter[str]] = defaultdict(Counter)
    publisher: dict[str, Counter[str]] = defaultdict(Counter)
    with path.open(newline="") as source:
        for index, row in enumerate(csv.DictReader(source)):
            if index >= train_rows:
                break
            attributed = int(row["is_attributed"])
            for destination, identifier in ((campaign, row["campaign_id"]), (publisher, row["publisher_id"])):
                destination[identifier]["clicks"] += 1
                destination[identifier]["attributed"] += attributed
    return dict(campaign), dict(publisher)


def build_features(
    path: Path,
    total_rows: int,
    campaign_stats: dict[str, dict[str, int]],
    publisher_stats: dict[str, dict[str, int]],
) -> tuple[np.ndarray, np.ndarray]:
    features = np.empty((total_rows, len(FEATURE_ORDER)), dtype=np.float32)
    labels = np.empty(total_rows, dtype=np.int8)
    engine = IncrementalClickFeatures(campaign_stats, publisher_stats)
    with path.open(newline="") as source:
        for index, row in enumerate(csv.DictReader(source)):
            enriched = engine.enrich(row)
            features[index] = vectorize(enriched)
            labels[index] = int(row["is_fraud"])
    return features, labels


def class_weight(labels: np.ndarray) -> float:
    positives = int(labels.sum())
    if positives == 0 or positives == len(labels):
        raise ValueError("Both positive and negative bootstrap labels are required for model training.")
    return (len(labels) - positives) / positives


def metrics(labels: np.ndarray, scores: np.ndarray) -> dict[str, float]:
    return {
        "roc_auc": round(float(roc_auc_score(labels, scores)), 6),
        "pr_auc": round(float(average_precision_score(labels, scores)), 6),
    }


def threshold_for_f1(labels: np.ndarray, scores: np.ndarray) -> tuple[float, float]:
    precision, recall, thresholds = precision_recall_curve(labels, scores)
    f1 = 2 * precision[:-1] * recall[:-1] / np.maximum(precision[:-1] + recall[:-1], 1e-12)
    best = int(np.argmax(f1))
    return float(thresholds[best]), float(f1[best])


def make_xgb(scale_pos_weight: float, n_estimators: int) -> xgb.XGBClassifier:
    return xgb.XGBClassifier(
        n_estimators=n_estimators,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.9,
        colsample_bytree=0.9,
        scale_pos_weight=scale_pos_weight,
        eval_metric="aucpr",
        random_state=42,
        n_jobs=4,
        tree_method="hist",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("data/clicks_sample.csv"))
    parser.add_argument("--models-dir", type=Path, default=Path("models"))
    parser.add_argument("--test-fraction", type=float, default=0.2)
    parser.add_argument("--n-estimators", type=int, default=120)
    args = parser.parse_args()

    if not 0 < args.test_fraction < 0.5:
        raise ValueError("--test-fraction must be between 0 and 0.5")

    total_rows = count_rows(args.input)
    split_index = int(total_rows * (1 - args.test_fraction))
    campaign_stats, publisher_stats = conversion_snapshots(args.input, split_index)
    features, labels = build_features(args.input, total_rows, campaign_stats, publisher_stats)
    x_train, x_test = features[:split_index], features[split_index:]
    y_train, y_test = labels[:split_index], labels[split_index:]
    weight = class_weight(y_train)

    logistic = LogisticRegression(
        class_weight="balanced", max_iter=500, solver="lbfgs", random_state=42
    )
    logistic_started = time.perf_counter()
    logistic.fit(x_train, y_train)
    logistic_seconds = time.perf_counter() - logistic_started
    logistic_metrics = metrics(y_test, logistic.predict_proba(x_test)[:, 1])

    primary = make_xgb(weight, args.n_estimators)
    primary_started = time.perf_counter()
    primary.fit(x_train, y_train)
    primary_seconds = time.perf_counter() - primary_started
    primary_scores = primary.predict_proba(x_test)[:, 1]
    primary_metrics = metrics(y_test, primary_scores)
    threshold, best_f1 = threshold_for_f1(y_test, primary_scores)

    # Incremental experiment: W1 receives an initial booster; W2 adds trees to
    # it. Cold training uses the identical W1+W2 history and test window.
    w1_end = split_index // 2
    initial = make_xgb(class_weight(y_train[:w1_end]), args.n_estimators // 2)
    warm_started = time.perf_counter()
    initial.fit(x_train[:w1_end], y_train[:w1_end])
    warm = make_xgb(class_weight(y_train[w1_end:]), args.n_estimators // 2)
    warm.fit(x_train[w1_end:], y_train[w1_end:], xgb_model=initial.get_booster())
    warm_seconds = time.perf_counter() - warm_started
    warm_metrics = metrics(y_test, warm.predict_proba(x_test)[:, 1])

    cold = make_xgb(weight, args.n_estimators)
    cold_started = time.perf_counter()
    cold.fit(x_train, y_train)
    cold_seconds = time.perf_counter() - cold_started
    cold_metrics = metrics(y_test, cold.predict_proba(x_test)[:, 1])

    args.models_dir.mkdir(parents=True, exist_ok=True)
    with (args.models_dir / "click_fraud_model.pkl").open("wb") as destination:
        pickle.dump(primary, destination)
    with (args.models_dir / "feature_list.pkl").open("wb") as destination:
        pickle.dump(FEATURE_ORDER, destination)
    (args.models_dir / "campaign_stats.json").write_text(
        json.dumps({"campaign": campaign_stats, "publisher": publisher_stats}, indent=2) + "\n"
    )
    report: dict[str, Any] = {
        "dataset": str(args.input),
        "rows": total_rows,
        "time_split": {"train_rows": split_index, "test_rows": total_rows - split_index},
        "positive_rate_train": round(float(y_train.mean()), 6),
        "positive_rate_test": round(float(y_test.mean()), 6),
        "feature_order": FEATURE_ORDER,
        "logistic_regression": {**logistic_metrics, "wall_seconds": round(logistic_seconds, 3)},
        "xgboost_primary": {
            **primary_metrics,
            "wall_seconds": round(primary_seconds, 3),
            "flag_threshold": round(threshold, 6),
            "validation_f1_at_threshold": round(best_f1, 6),
        },
        "incremental_experiment": {
            "warm_start": {**warm_metrics, "wall_seconds": round(warm_seconds, 3)},
            "cold_w1_w2": {**cold_metrics, "wall_seconds": round(cold_seconds, 3)},
        },
    }
    (args.models_dir / "training_metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
