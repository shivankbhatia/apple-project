"""
Converts a fraud model to CoreML format for the SwiftUI app.

PLACEHOLDER MODE (default): trains a small XGBoost classifier on random data,
with the exact same feature schema your real Project 1 model will use — and
using XGBoost itself (not a stand-in algorithm), so the conversion path you
test now is the *exact* path you'll use for the real model later.

SWAP-IN LATER: once your XGBoost model from Project 1 is trained, replace
`train_placeholder_model()` with a load of your real trained model
(`xgb.Booster().load_model(...)` or your sklearn-wrapper `.get_booster()`),
keep FEATURE_NAMES identical, and re-run. Nothing downstream (Swift code)
needs to change as long as feature names/order stay the same.
"""

import numpy as np
import coremltools as ct
import xgboost as xgb

# ---------------------------------------------------------------------------
# SCHEMA — locked contract between Project 1 (model) and Project 2 (app).
# Edit this list to match your real feature set from the fraud-lambda
# pipeline, then re-run this script. Order matters — must match training order.
# ---------------------------------------------------------------------------
FEATURE_NAMES = [
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

OUTPUT_PATH = "FraudModel.mlmodel"


def load_real_model(model_path: str):
    """Load the trained XGBoost model from Project 1."""
    import pickle
    with open(model_path, 'rb') as f:
        model = pickle.load(f)
    return model


def convert_to_coreml(sk_model, feature_names, output_path):
    booster = sk_model.get_booster()
    booster.feature_names = feature_names
    coreml_model = ct.converters.xgboost.convert(
        booster,
        feature_names=feature_names,
        mode="classifier",
        class_labels=[0, 1],
    )
    coreml_model.author = "Shivank"
    coreml_model.short_description = "Ad-click fraud risk classifier — real model from Project 1"
    coreml_model.save(output_path)
    print(f"Saved CoreML model to {output_path}")
    return coreml_model


if __name__ == "__main__":
    model = load_real_model("/Users/shivank/Projects/appleproject/fraud_lambda/models/click_fraud_model.pkl")
    convert_to_coreml(model, FEATURE_NAMES, OUTPUT_PATH)
    print("Model converted successfully")
