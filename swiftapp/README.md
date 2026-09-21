# Project 2 — On-Device Ad Fraud Triage App

Everything here is written and (Python side) tested. The Swift side is written
but **not compiled** — there's no Xcode/Swift toolchain in the environment I
run in, so you'll need to build it in Xcode on your Mac. I'll walk you through
that below; it should be a straight drag-and-drop, not real coding.

## What's in here

```
python/
  convert_model.py   — trains a placeholder XGBoost model + converts to CoreML
  parity_test.py      — compares XGBoost vs CoreML predictions (run on macOS)
  FraudModel.mlmodel   — the converted placeholder model (already generated)
swift/
  FraudModels.swift    — ClickBatch struct, RiskLevel enum, mock data
  FraudPredictor.swift — CoreML inference wrapper
  ContentView.swift    — list view (flagged batches, risk badges)
  BatchDetailView.swift— detail view (feature breakdown)
  Project2App.swift    — app entry point
```

## Verified already
`python/convert_model.py` ran successfully and produced `FraudModel.mlmodel`.
Sample placeholder fraud probabilities from the run: `[0.943, 0.961, 0.929,
0.879, 0.95]` — model loads, trains, and converts cleanly. One warning is
expected and harmless: coremltools hasn't been tested against the newest
xgboost release, but conversion worked fine.

## What you need to do (Xcode side)

1. **Create the Xcode project**
   - Xcode → New Project → macOS or iOS → App → interface: SwiftUI
   - Name it whatever you like (e.g. `FraudTriage`)

2. **Drag in the model**
   - Drag `FraudModel.mlmodel` from `python/` into the Xcode project navigator
   - Click it once in Xcode — confirm it shows 6 inputs (click_velocity,
     fingerprint_entropy, click_to_conv_ratio, geo_mismatch, time_to_click_ms,
     ip_reuse_rate) and a classifier output. Xcode auto-generates the
     `FraudModel` Swift class from this — that's what `FraudPredictor.swift`
     calls into.

3. **Drag in the Swift files**
   - Drag all 5 files from `swift/` into the project navigator
   - Delete the default `ContentView.swift` Xcode generates for you first (to
     avoid a naming collision), then add the one from `swift/`

4. **Run it**
   - Cmd+R. You should see a list of 3 mock flagged batches, sorted by risk,
     tap into any one for the feature breakdown.

## Running the parity test (on your Mac, after Xcode setup or before — doesn't need Xcode)
```
cd python
python3 -m venv venv && source venv/bin/activate
pip install coremltools xgboost scikit-learn numpy
python3 parity_test.py
```
This only runs on macOS — coremltools' `.predict()` needs the CoreML
framework, which isn't available on Linux (that's also why I couldn't run
this test myself in this sandbox — I ran the conversion, not this file).

## Swapping in your real Project 1 model later
1. In `convert_model.py`, replace `train_placeholder_model()` with your real
   trained XGBoost model (same `FEATURE_NAMES` list, same order)
2. Re-run `convert_model.py` — it overwrites `FraudModel.mlmodel`
3. In Xcode, delete the old `FraudModel.mlmodel` reference and drag in the new one
4. Re-run `parity_test.py` against real held-out data, record the max-diff
   number for your write-up
5. No Swift code changes needed, as long as `FEATURE_NAMES` didn't change

## What to actually understand (not just run)
- **`convert_model.py`**: `coremltools.converters.xgboost.convert()` is what
  turns your trained booster into a `.mlmodel` — this is Phase 1 from the plan.
- **`parity_test.py`**: this is Phase 2 — the artifact that proves the CoreML
  version didn't silently diverge from the Python model during conversion.
- **`FraudPredictor.swift`**: the feature values you pass into
  `FraudModelInput(...)` must be in the same order/units as `FEATURE_NAMES` —
  if Project 1's feature engineering changes, this struct (and the schema
  list in `convert_model.py`) is what you update.
- **`ContentView.swift` / `BatchDetailView.swift`**: standard SwiftUI
  list/detail pattern — `NavigationStack` + `NavigationLink` + `List`. Nothing
  fraud-specific about the UI code itself; worth understanding as reusable
  SwiftUI structure beyond this project.
