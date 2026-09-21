# Dual-Model System Implementation Plan

## **Phase 1: Build Ad-Aggregated Dataset**

### Checklist:

- [ ] **1.1** Load 1M clicks from Project 1 parquet
  - File: `fraud_lambda/data/batch/batch_scored_clicks.parquet`
  - Output: DataFrame with all click-level data
  
- [ ] **1.2** Aggregate by `ad_id`
  - Group clicks by ad_id
  - Compute: total_clicks, unique_ips, unique_devices, fraud_rate, conversion_rate
  - Output: Ad-level DataFrame (214 ads)

- [ ] **1.3** Compute ad-level features (20+ features)
  - Fraud patterns: fraud_click_rate, bot_ip_percentage, high_entropy_ips
  - Performance: conversion_rate, install_rate, rapid_fire_rate
  - Geographic: country_diversity, suspicious_country_rate
  - Output: Feature matrix (214 ads × 20 features)

- [ ] **1.4** Create labels
  - Define: Ad is fraudulent if fraud_click_rate > X% (e.g., 50%)
  - Output: Binary labels (214 ads, labeled 0 or 1)

- [ ] **1.5** Save ad dataset
  - Output: `ad_fraud_data.csv` and `ad_fraud_labels.pkl`
  - Ready for training

---

## **Phase 2: Train Ad-Level XGBoost Model**

### Checklist:

- [ ] **2.1** Load ad-aggregated data
  - Read `ad_fraud_data.csv`
  - Load labels from `ad_fraud_labels.pkl`

- [ ] **2.2** Split train/test
  - 80% train, 20% test
  - Stratified split (maintain fraud distribution)

- [ ] **2.3** Train XGBoost classifier
  - Same hyperparameters as Model 1 for consistency
  - n_estimators=120, max_depth=6, learning_rate=0.1
  - eval_metric='aucpr'
  - Output: Trained booster

- [ ] **2.4** Evaluate on test set
  - Compute ROC-AUC, PR-AUC, F1 scores
  - Compare against Model 1 metrics
  - Output: `ad_model_metrics.json`

- [ ] **2.5** Save trained model
  - Output: `ad_fraud_model.pkl`
  - Store feature list: `ad_feature_names.pkl`

---

## **Phase 3: Convert to CoreML**

### Checklist:

- [ ] **3.1** Load trained ad model
  - Read `ad_fraud_model.pkl`
  - Extract booster

- [ ] **3.2** Set feature names
  - booster.feature_names = ad_feature_names
  - Order matters!

- [ ] **3.3** Convert to CoreML
  - Use coremltools.converters.xgboost.convert()
  - mode='classifier', class_labels=[0, 1]
  - Output: CoreML model object

- [ ] **3.4** Add metadata
  - author, description, version
  - Input/output specs

- [ ] **3.5** Save CoreML model
  - Output: `AdFraudModel.mlmodel` (in swiftapp/)
  - Ready for Xcode bundle

- [ ] **3.6** Verify model
  - Load model, check input/output shapes
  - Test with sample data
  - Output: Conversion validation report

---

## **Phase 4: Create Ad Data Aggregator for SwiftApp**

### Checklist:

- [ ] **4.1** Create Python exporter script
  - Reads parquet, aggregates by ad_id
  - Computes 20 ad-level features
  - Outputs: `ads_for_prediction.csv` with metadata

- [ ] **4.2** Create Swift data structures
  - `AdCampaign` struct (replaces `ClickBatch`)
  - Fields: adId, campaignName, totalClicks, uniqueIPs, fraudRate, etc.
  - Mock data for testing

- [ ] **4.3** Create AdDataLoader (Swift)
  - Similar to existing DataLoader
  - Parses `ads_for_prediction.csv`
  - Returns `[AdCampaign]`

- [ ] **4.4** Create AdPredictor (Swift)
  - Wraps CoreML `AdFraudModel`
  - Input: AdCampaign
  - Output: fraud probability (0-1)

- [ ] **4.5** Test loading and prediction
  - Load sample ads
  - Run predictions
  - Verify output range [0, 1]

---

## **Phase 5: Build Ad-Level SwiftUI View**

### Checklist:

- [ ] **5.1** Create `AdFraudPredictor` view
  - Similar structure to `RealTimePredictor`
  - Shows: adId, totalClicks, uniqueIPs, fraudRate

- [ ] **5.2** Add prediction section
  - Show server-side prediction (if available)
  - Show on-device CoreML prediction
  - Show parity check (delta)

- [ ] **5.3** Add navigation
  - Previous/Next buttons to browse ads
  - Counter: "Ad 1 of 214"
  - Reset prediction on navigation

- [ ] **5.4** Add visual indicators
  - Green (clean): fraud_score < 0.3
  - Orange (suspicious): 0.3 ≤ fraud_score < 0.7
  - Red (flagged): fraud_score ≥ 0.7

- [ ] **5.5** Test UI
  - Load ads, compute predictions
  - Navigate through ads
  - Verify all data displays correctly

---

## **Phase 6: Reconciliation & Sync System**

### Checklist:

- [ ] **6.1** Create reconciliation logger
  - Track device predictions
  - Log: adId, timestamp, deviceScore, decision

- [ ] **6.2** Implement comparison logic
  - Store server batch predictions (in CSV)
  - Compare: device_score vs server_score
  - Calculate drift (KL divergence, MAE)

- [ ] **6.3** Set drift thresholds
  - Define: When to trigger model update (e.g., drift > 15%)
  - Output: Recommendation to sync new model

- [ ] **6.4** Create model update mechanism
  - Download new `AdFraudModel.mlmodel` from server
  - Replace old model in app
  - Log update event

- [ ] **6.5** Batch reconciliation script (Python)
  - Retrain Model 2 on latest data (daily)
  - Compare device logs vs server batch predictions
  - Generate new CoreML if drift > threshold
  - Output: Metrics report

- [ ] **6.6** Test reconciliation flow
  - Run batch retraining
  - Measure drift
  - Verify model update trigger

---

## **Phase 7: Integration & Testing**

### Checklist:

- [ ] **7.1** Add both models to Xcode
  - `FraudModel.mlmodel` (per-click, existing)
  - `AdFraudModel.mlmodel` (per-ad, new)
  - Both in bundle

- [ ] **7.2** Create tab-based UI
  - Tab 1: Per-Click Fraud (existing `RealTimePredictor`)
  - Tab 2: Per-Ad Fraud (new `AdFraudPredictor`)
  - Switch between models

- [ ] **7.3** Update Project2App
  - Show both models available
  - Persist user's last view preference

- [ ] **7.4** Test on simulator
  - Load ad data, run predictions
  - Verify parity check calculation
  - Test navigation and UI

- [ ] **7.5** Test on device
  - Build for physical iOS device
  - Verify CoreML inference speed
  - Check memory usage

- [ ] **7.6** Create demo walkthrough
  - Document: "How to use dual-model system"
  - Show: click-level vs ad-level predictions
  - Explain: Reconciliation flow

---

## **Phase 8: Documentation & Deployment**

### Checklist:

- [ ] **8.1** Document Model 2 architecture
  - Feature definitions (20 features)
  - Training process
  - Performance metrics

- [ ] **8.2** Document reconciliation process
  - How often models sync
  - Drift calculation method
  - Update trigger thresholds

- [ ] **8.3** Create user guide
  - How to interpret per-click vs per-ad predictions
  - What each metric means
  - How parity check works

- [ ] **8.4** Prepare for production
  - Code review checklist
  - Performance benchmarks
  - Security audit

- [ ] **8.5** Plan ongoing maintenance
  - Weekly model retraining schedule
  - Monthly performance reviews
  - Quarterly model updates to devices

- [ ] **8.6** Success metrics
  - Model 2 accuracy on held-out ads
  - Parity between on-device and server
  - App performance (latency, memory)

---

## **Timeline Estimate**

| Phase | Tasks | Estimated Time |
|-------|-------|-----------------|
| 1 | Build ad dataset | 1-2 hours |
| 2 | Train XGBoost | 1 hour |
| 3 | Convert to CoreML | 30 mins |
| 4 | Create Swift structures | 2-3 hours |
| 5 | Build UI | 2-3 hours |
| 6 | Reconciliation system | 2-3 hours |
| 7 | Integration & testing | 2-3 hours |
| 8 | Documentation | 1-2 hours |
| **TOTAL** | | **12-18 hours** |

---

## **Success Criteria**

- ✅ Ad-level dataset created (214 ads aggregated)
- ✅ Model 2 trained with ROC-AUC > 0.85
- ✅ CoreML conversion validated (< 10% drift from Python)
- ✅ SwiftUI shows both per-click and per-ad predictions
- ✅ Reconciliation system tracks drift
- ✅ App runs on device with < 1 second prediction latency
- ✅ Documentation complete with architecture diagrams
- ✅ Dual-model system ready for production deployment

---

## **Starting Now: Phase 1**

Ready to build ad-aggregated dataset and train Model 2!
