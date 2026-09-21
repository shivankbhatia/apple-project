"""
Prediction-parity test: compares raw XGBoost predictions against the
converted CoreML model's predictions on the same input rows.

IMPORTANT: coremltools' .predict() only works on macOS (it calls into the
CoreML framework). This script will not run in a Linux container — run it
on your Mac after converting the model there (or after copying the
.mlmodel + your XGBoost model over).

Usage:
    python3 parity_test.py
"""

import numpy as np
import coremltools as ct
import pickle
from convert_model import FEATURE_NAMES, OUTPUT_PATH

TOLERANCE = 1e-3  # acceptable absolute difference between the two models' scores


def run_parity_test():
    # --- Load the real trained model from Project 1 ---
    model_path = "/Users/shivank/Projects/appleproject/fraud_lambda/models/click_fraud_model.pkl"
    with open(model_path, 'rb') as f:
        xgb_model = pickle.load(f)
    
    # --- Use a sample from the training data for parity test ---
    # Load the sample data used in training
    import csv
    data_path = "/Users/shivank/Projects/appleproject/fraud_lambda/data/clicks_sample.csv"
    
    # For simplicity, we'll generate synthetic test data that matches the feature schema
    # In production, you'd use real held-out test data
    rng = np.random.default_rng(42)
    n_test = 50
    n_features = len(FEATURE_NAMES)
    X_test = rng.random((n_test, n_features))

    # --- original model predictions ---
    xgb_probs = xgb_model.predict_proba(X_test)[:, 1]

    # --- CoreML model predictions ---
    coreml_model = ct.models.MLModel(OUTPUT_PATH)
    coreml_probs = []
    for row in X_test:
        input_dict = {name: float(val) for name, val in zip(FEATURE_NAMES, row)}
        result = coreml_model.predict(input_dict)
        # classProbability is a dict like {0: p0, 1: p1} for classifiers
        coreml_probs.append(result["classProbability"][1])
    coreml_probs = np.array(coreml_probs)

    # --- compare ---
    diffs = np.abs(xgb_probs - coreml_probs)
    max_diff = diffs.max()
    mismatches = np.where(diffs > TOLERANCE)[0]

    print(f"Tested {len(X_test)} rows")
    print(f"Max absolute difference: {max_diff:.6f}")
    print(f"Tolerance: {TOLERANCE}")
    print(f"Rows exceeding tolerance: {len(mismatches)}")

    if len(mismatches) > 0:
        print("\nMismatched rows:")
        for i in mismatches:
            print(f"  row {i}: xgb={xgb_probs[i]:.4f}  coreml={coreml_probs[i]:.4f}  diff={diffs[i]:.4f}")
        print("\nRESULT: FAIL — investigate before shipping this model.")
    else:
        print("\nRESULT: PASS — CoreML predictions match XGBoost within tolerance.")

    return {
        "max_diff": float(max_diff),
        "n_mismatches": int(len(mismatches)),
        "tolerance": TOLERANCE,
        "n_tested": len(X_test),
    }


if __name__ == "__main__":
    run_parity_test()
