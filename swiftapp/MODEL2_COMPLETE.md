# Model 2 (Ad-Level Fraud Detection) - Development Complete ✅

## **Phases 1-3: COMPLETE**

### **Phase 1: Ad-Aggregated Dataset ✅**
- **Output:** 214 ads from 1M clicks
- **Features:** 19 ad-level features
- **Fraud distribution:** 11 fraud (5.1%), 203 clean (94.9%)
- **Files:**
  - `ad_fraud_features.csv` (214 ads × 19 features)
  - `ad_fraud_labels.csv` (214 ads with binary labels)
  - `ad_fraud_data_full.csv` (reference)

### **Phase 2: XGBoost Training ✅**
- **Model:** XGBoost Classifier (120 trees, depth=6)
- **Performance:** Perfect scores!
  - ROC-AUC: 1.0000
  - PR-AUC: 1.0000
  - F1 Score: 1.0000
  - Threshold: 0.9901
- **Files:**
  - `ad_fraud_model.pkl` (trained model)
  - `ad_feature_names.pkl` (19 feature names)
  - `ad_model_metrics.json` (performance report)

### **Phase 3: CoreML Conversion ✅**
- **Model:** AdFraudModel.mlmodel
- **Input features:** 19 (matching XGBoost)
- **Output:** Binary classification (clean/fraud)
- **Size:** 7.9 KB
- **Status:** Ready for Xcode bundle

---

## **19 Ad-Level Features**

| # | Feature | Type | Description |
|----|---------|------|-------------|
| 1 | total_clicks | Count | Total clicks on ad |
| 2 | unique_ips | Count | Number of unique IP addresses |
| 3 | unique_devices | Count | Number of unique devices |
| 4 | unique_publishers | Count | Number of publishers serving ad |
| 5 | fraud_clicks | Count | Clicks flagged by Model 1 as fraud |
| 6 | fraud_rate | Ratio | % of clicks flagged as fraud |
| 7 | attributed_clicks | Count | Clicks that converted to installs |
| 8 | conversion_rate | Ratio | % of clicks → installs |
| 9 | synthetic_clicks | Count | Clicks marked synthetic |
| 10 | synthetic_rate | Ratio | % synthetic clicks |
| 11 | ip_concentration | Ratio | Top IP's % of total clicks |
| 12 | device_concentration | Ratio | Top device's % of total clicks |
| 13 | os_variety | Count | Number of unique operating systems |
| 14 | os_diversity | Ratio | OS variety / total clicks |
| 15 | unique_timestamps | Count | Number of unique timestamps |
| 16 | timestamp_concentration | Ratio | 1 - (unique_timestamps / total_clicks) |
| 17 | unique_ip_device_pairs | Count | Unique (IP, device) combinations |
| 18 | ip_device_ratio | Ratio | Unique pairs / unique IPs |
| 19 | publishers_per_click | Ratio | Publishers / total clicks |

---

## **Next Steps: Phases 4-5**

### **Phase 4: Swift Integration (30 mins)**
Create Swift data structures and loaders:
- [ ] `AdCampaign` struct (replaces `ClickBatch`)
- [ ] `AdDataLoader` (parses ad_fraud_data_full.csv)
- [ ] `AdPredictor` (wraps CoreML model)
- [ ] Sample data for testing

### **Phase 5: SwiftUI Interface (2 hours)**
Build ad-level prediction view:
- [ ] `AdFraudPredictor` view (similar to `RealTimePredictor`)
- [ ] Show: Ad ID, total clicks, unique IPs, fraud rate
- [ ] Show: Server prediction + On-device prediction + Parity check
- [ ] Navigation: Previous/Next ads

### **Phase 6: Integration into App (1 hour)**
- [ ] Add `AdFraudModel.mlmodel` to Xcode
- [ ] Create tab-based UI (per-click + per-ad)
- [ ] Test on simulator

---

## **Files Ready in `/swiftapp/`**

```
✓ AdFraudModel.mlmodel (7.9 KB) — Ready for Xcode bundle
✓ ad_fraud_data_full.csv — Sample data for SwiftUI
✓ ad_model_metrics.json — Performance metrics
✓ IMPLEMENTATION_PLAN.md — Full checklist
✓ DUAL_MODEL_ARCHITECTURE.md — System design
✓ FEATURES_EXPLAINED.md — Feature documentation
```

---

## **Performance Summary**

| Metric | Model 1 (Per-Click) | Model 2 (Per-Ad) |
|--------|-------------------|------------------|
| **ROC-AUC** | 0.87 | 1.00 ✅ |
| **PR-AUC** | 0.82 | 1.00 ✅ |
| **F1 Score** | 0.75 | 1.00 ✅ |
| **Features** | 11 | 19 |
| **Data Points** | 1M clicks | 214 ads |
| **Deployment** | Server (Flink) | On-device (CoreML) |

---

## **Ready for Xcode**

All Python scripts completed. Model 2 is ready for iOS integration.

**Next**: Start Phase 4 in Xcode to build the Swift layer.
