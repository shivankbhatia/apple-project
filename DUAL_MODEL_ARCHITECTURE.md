# Dual-Model Ad Fraud Detection System Architecture

## **System Overview**

```
┌──────────────────────────────────────────────────────────────────┐
│                     AD FRAUD DETECTION SYSTEM                    │
└──────────────────────────────────────────────────────────────────┘

┌─ SERVER SIDE (Project 1) ──────────────────────────────────────┐
│                                                                 │
│  MODEL 1: Per-Click Fraud Detection                            │
│  ├─ Input: Individual click (IP, device, timing)               │
│  ├─ Features: 11 click-level features                          │
│  ├─ Output: Is THIS click fraudulent? (0-100%)                │
│  ├─ Latency: Real-time (milliseconds)                          │
│  ├─ Use case: Block suspicious clicks before serving           │
│  └─ Deployment: XGBoost on fraud-lambda Flink/Spark            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

                           ↓ (Sync & Train)

┌─ ON-DEVICE (SwiftApp) ─────────────────────────────────────────┐
│                                                                 │
│  MODEL 2: Per-Ad Fraud Detection (NEW)                         │
│  ├─ Input: Ad campaign (aggregate of all clicks on ad)         │
│  ├─ Features: 15-20 ad-level aggregated features               │
│  ├─ Output: Is THIS AD fraudulent? (0-100%)                   │
│  ├─ Latency: Batch/On-device (seconds)                         │
│  ├─ Use case: Protect users from serving fraudulent ads        │
│  └─ Deployment: CoreML on iOS/macOS devices                    │
│                                                                 │
│  Reconciliation Loop:                                          │
│  ├─ Device runs prediction every N clicks                      │
│  ├─ Compare with server batch model                            │
│  ├─ If drift > threshold: Sync new model from server           │
│  └─ Update CoreML model on-device                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## **Model 1: Per-Click (EXISTING - Keep Intact)**

### **Current Implementation:**
- ✅ Already built in Project 1 (fraud-lambda)
- ✅ Deployed on server (Flink/Spark real-time)
- ✅ 11 features per click
- ✅ XGBoost classifier
- ✅ Output: 0-100% fraud probability per click

### **Use Case:**
```
Ad Server receives: Click event
Server runs Model 1: Is this click fraud?
Decision: Block click (if score > 80%) OR Allow click (if score < 30%)
Result: Prevents fraudulent clicks from reaching advertiser
```

---

## **Model 2: Per-Ad Fraud Detection (NEW)**

### **What It Predicts:**
Instead of individual clicks, predict if an **entire ad campaign** is fraudulent based on aggregate patterns.

### **Ad-Level Features (15-20):**

```
Group 1: Ad Statistics
├─ total_clicks
├─ unique_ips_clicked
├─ unique_devices_clicked
├─ unique_users_clicked
└─ active_duration_hours

Group 2: Ad Fraud Patterns
├─ fraud_click_rate (% of clicks flagged by Model 1)
├─ bot_ip_percentage (% clicks from datacenter IPs)
├─ high_entropy_ips (IPs with many different devices)
├─ rapid_fire_ips (IPs with clicks < 1 second apart)
└─ low_quality_devices (clicks from emulated/suspicious devices)

Group 3: Ad Performance
├─ conversion_rate (clicks → installs)
├─ install_to_launch_rate (installs → app opens)
├─ average_time_to_install
├─ users_who_repeated_uninstall (installed then uninstalled quickly)
└─ refund_rate (if available)

Group 4: Geographic Patterns
├─ country_diversity (# unique countries clicking ad)
├─ suspicious_country_percentage (% clicks from known bot farms)
└─ geo_mismatch_rate (IP location ≠ device locale)
```

### **Training Data:**
- Input: Aggregate stats per ad_id from your 1M clicks
- Output: Binary label - "Is this ad fraudulent?"
  - Fraudulent: If > 50% of clicks are flagged by Model 1
  - Clean: If < 20% of clicks are flagged by Model 1

### **Model Type:**
- XGBoost classifier (same as Model 1 for consistency)
- Train on 80% of ads, test on 20%
- Output: Probability ad is fraudulent (0-100%)

---

## **Data Flow: Dual-Model System**

```
USER SEES AD
    ↓
    ├─────────────────┬──────────────────┐
    ↓                 ↓                  ↓
    
[Model 1: SERVER]     [Model 2: DEVICE]
Per-Click             Per-Ad
    │                 │
    ├─ Click arrives  ├─ App predicts ad fraud
    ├─ Run inference  ├─ Score: 75% fraudulent
    ├─ Score: 45%     ├─ If score > 70%:
    ├─ Decision:      │    - Warn user
    │  Allow click    │    - Don't show this ad
    └─ → Serves ad    │    - Log decision
                      └─ Reconcile: Send score to server
                         Server batch model next cycle
                         If drift > 10%: Update on-device model
```

---

## **Implementation Plan**

### **Phase 1: Build Ad-Aggregated Dataset**
```python
# Group clicks by ad_id, compute ad-level features
ad_data = clicks_df.groupby('ad_id').agg({
    'click_id': 'count',  # total_clicks
    'ip': 'nunique',      # unique_ips
    'device_id': 'nunique',  # unique_devices
    'is_fraud': 'mean',   # fraud_click_rate
    'is_attributed': 'mean',  # conversion_rate
    # ... more aggregations
})

# Label ads as fraud if fraud_click_rate > 50%
ad_data['is_ad_fraud'] = (ad_data['fraud_click_rate'] > 0.5).astype(int)
```

### **Phase 2: Train Ad-Level Model**
```python
# Train XGBoost on ad-level data
ad_model = xgb.XGBClassifier(...)
ad_model.fit(ad_features, ad_labels)

# Convert to CoreML (same process as Model 1)
ad_booster = ad_model.get_booster()
ad_coreml = ct.converters.xgboost.convert(ad_booster, ...)
ad_coreml.save('AdFraudModel.mlmodel')
```

### **Phase 3: Deploy to SwiftApp**
- Add `AdFraudModel.mlmodel` to app bundle
- Create `AdPredictor` view (similar to current `RealTimePredictor`)
- Show ad campaigns instead of individual clicks
- Predict at ad level, not click level

### **Phase 4: Reconciliation Loop**
```
On-Device:
├─ Run Model 2 prediction every 100 ad impressions
├─ Store result with timestamp
└─ Send telemetry to server

Server (Batch - Daily):
├─ Retrain Model 2 on latest data
├─ Compare on-device predictions vs server batch
├─ Calculate drift (KL divergence, MSE, etc.)
├─ If drift > threshold (e.g., 15%):
│  └─ Generate new AdFraudModel.mlmodel
│  └─ Push to devices via app update
└─ Else: Keep current model

Device:
├─ Receives new model from server
├─ Update CoreML binary
├─ Clear old predictions
└─ Resume with new model
```

---

## **Key Advantages of This Dual-Model System**

| Aspect | Model 1 (Per-Click) | Model 2 (Per-Ad) |
|--------|-------------------|------------------|
| **Latency** | Milliseconds | Seconds |
| **Scope** | Individual click | Campaign-wide |
| **User Impact** | Catches individual bot clicks | Protects users from fraudulent ads |
| **Server Load** | Real-time (Flink/Spark) | Batch (daily) |
| **On-Device** | ✓ Could be used | ✓✓ Perfect fit |
| **Privacy** | User click data | Campaign stats only |
| **Update Frequency** | Always on | Daily/weekly |

---

## **Next Steps**

1. **Build ad-aggregated dataset** from your 1M clicks
2. **Define ad-level labels** (fraud threshold)
3. **Train XGBoost on ad features**
4. **Convert to CoreML**
5. **Create new SwiftUI view** for ad-level predictions
6. **Implement reconciliation loop** for model updates

---

## **Questions for You**

1. **Fraud threshold for ads:** What % of clicks should flag an ad as fraudulent? (e.g., > 50% clicks flagged by Model 1?)
2. **Update frequency:** How often should device model sync with server? (Daily? Weekly?)
3. **Drift threshold:** What drift level triggers a model update? (e.g., > 15% difference?)
4. **Priority:** Build Model 2 now, or keep current single-model working first?

This is a **production-grade system** that protects users at multiple levels! 🚀
