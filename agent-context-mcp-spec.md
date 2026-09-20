# Apple Ad Platforms Portfolio — Implementation Plans

Two projects, built to hit what Apple's Ad Platforms JDs actually ask for: scale, low latency, privacy-by-design, streaming + batch data pipelines, and applied ML on solid infra.

---

## Project 1: Ad-Click Fraud Detection (retarget of `fraud-lambda`)

### Goal
Repurpose the existing lambda-architecture fraud system from generic transaction fraud to **ad-click fraud** — bot traffic, click farms, and invalid click patterns. Same infra, new domain, new feature set.

### Architecture (unchanged core)
```
Kafka (click event stream)
   ├─ Speed layer:  PyFlink → real-time fraud score → serving table
   └─ Batch layer:  Spark → Delta Lake → Hive → model retraining
                              ↓
                        XGBoost classifier
```

### What changes
- **Event schema**: replace transaction fields with click events — `click_id`, `ad_id`, `device_id`, `ip`, `user_agent`, `timestamp`, `campaign_id`, `referrer`, `click_to_install_delta` (if attributable).
- **Feature engineering** (ad-fraud specific):
  - Click velocity per IP/device (sliding windows: 1min/5min/1hr)
  - Device/IP fingerprint entropy (click farms reuse fingerprints)
  - Time-to-click distribution (bots click unnaturally fast/uniformly)
  - Click-to-conversion ratio per publisher/campaign (fraud farms have near-zero conversion)
  - Geo-IP mismatch vs. device locale
- **Labels**: use public ad-fraud datasets (e.g., TalkingData AdTracking Kaggle set) to bootstrap; simulate click-farm traffic patterns for synthetic positives if needed.
- **Model**: keep XGBoost + your incremental retraining exploration (warm-start / sliding window) — click fraud patterns drift fast (new bot farms), so this becomes a *feature*, not just an experiment.

### Milestones
1. Swap schema + Kafka producer to emit synthetic ad-click stream
2. Rebuild feature pipeline in PyFlink (velocity + entropy features)
3. Retrain XGBoost on new feature set, re-baseline p50/p95/p99 latency
4. Add a monitoring view: fraud rate by campaign/publisher over time
5. Write up: before/after latency, precision/recall, and why lambda architecture fits (speed layer blocks obviously-fraudulent clicks before spend; batch layer catches sophisticated patterns after the fact)

### Implementation phase status

- [x] Phase 0 — infrastructure layout, explicit Kafka topics, Hive warehouse mount, feature-package scaffold, and host requirements
- [x] Phase 1 — TalkingData sample, bootstrap labels, and EDA
- [x] Phase 2 — shared feature implementation and parity tests
- [x] Phase 3 — baseline model and incremental retraining
- [ ] Phase 4 — click producer and schema validation
- [ ] Phase 5 — PyFlink scorer and alerts
- [ ] Phase 6 — Spark retraining, Hive, and Delta
- [ ] Phase 7 — reconciliation, drift, and latency reporting
- [ ] Phase 8 — monitoring dashboard
- [ ] Phase 9 — documentation and demo export

### Reused assets
Kafka setup, PyFlink/Spark jobs, Delta Lake schema patterns, latency instrumentation (`latency_ms`), and your incremental-retraining research all carry over directly — this is largely a feature-engineering + relabeling effort, not a rebuild.

### Why it maps to Apple Ad Platforms
JDs explicitly call for Kafka, Spark, streaming + batch pipelines, and "applied machine learning... a plus." This project demonstrates all of it in the exact domain (ad fraud / invalid traffic) their infra teams own.

---

## Project 2: On-Device Ad Fraud Triage App (CoreML + SwiftUI)

### Goal
A native macOS/iOS app for reviewing flagged ad-fraud events — entirely on-device. Demonstrates Apple-platform fluency (Swift, CoreML) layered on top of Project 1's model, and reflects Apple's actual privacy stance in advertising (SKAdNetwork/AdAttributionKit-style: no raw data leaves the device). Deliberately scoped small: ML deployment + on-device inference, no LLM/backend/cloud surface area.

### Architecture
```
Project 1's trained XGBoost model
        ↓ (convert via coremltools)
   CoreML model (.mlpackage)
        ↓
SwiftUI app (macOS/iOS)
   └─ CoreML inference: scores flagged click batches on-device
```

### Components
1. **Model conversion**: `coremltools` to convert the XGBoost fraud model to CoreML format (`.mlpackage`).
2. **Prediction-parity testing**:
   ```
   Python XGBoost
        ↓
   Predictions
        ↕ compare
   CoreML Model
        ↓
   On-device predictions
   ```
   Run the same held-out batch through both models; assert CoreML output scores stay within an acceptable numerical tolerance (e.g. `abs(diff) < 1e-4` or a relative tolerance) of the original XGBoost scores. Log any mismatches — this is the artifact that proves the conversion is trustworthy, not just "it runs."
3. **SwiftUI app**:
   - List view of flagged click batches (mock data or exported from Project 1's Delta Lake output)
   - Detail view per batch: fraud score, risk level (e.g. low/medium/high banding on the score), key fraud features (click velocity, device/IP fingerprint entropy, click-to-conversion ratio, geo mismatch)
   - Sort/filter by fraud score, campaign, publisher
4. **Privacy framing**: document that inference runs fully locally via CoreML — no server round-trip for prediction. Short write-up on the on-device processing design and why it matters for ad-privacy architecture.

### Out of scope (explicitly)
No Foundation Models/on-device LLM, no prompt engineering, no RAG, no new ML model, no backend, no additional cloud infrastructure.

### Milestones
1. Export a sample of flagged/unflagged batches from Project 1
2. Convert XGBoost → CoreML
3. Build the prediction-parity test harness, validate tolerance
4. Build SwiftUI list/detail UI (static data first)
5. Wire up CoreML inference for live scoring in-app
6. Write up: parity results + on-device/privacy design rationale

### Why it maps to Apple Ad Platforms
Combines a real ML/data pipeline (Project 1) with native Apple-platform delivery (Swift/CoreML) and a rigorous parity-testing step — signals you can take a backend ML system and ship it on-device correctly, not just "get it to compile."

---

## Suggested sequencing
Build Project 1 first (it's a retarget of existing work — fastest win), export a clean sample dataset from it, then build Project 2 on top. This also gives you a natural narrative for interviews: "I built the data pipeline, then validated and shipped it on-device."
