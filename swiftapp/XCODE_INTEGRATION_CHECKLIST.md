# Phase 4-5: Swift Integration - Xcode Checklist

## **Files Created (Ready for Xcode Bundle)**

### Swift Files (4 new + 1 updated):
- ✅ `AdModels.swift` — AdCampaign struct (19 features)
- ✅ `AdDataLoader.swift` — Loads ad_fraud_data_full.csv
- ✅ `AdPredictor.swift` — CoreML wrapper for Model 2
- ✅ `AdFraudPredictor.swift` — SwiftUI main UI (319 lines)
- ✅ `Project2App.swift` — Updated to show tabbed view

### Data Files (Ready for Bundle):
- ✅ `ad_fraud_data_full.csv` — 214 ads × 19 features
- ✅ `AdFraudModel.mlmodel` — CoreML model (7.9 KB)

### Reference Files:
- ✅ `ad_model_metrics.json` — Performance report
- ✅ `ad_fraud_model.pkl` — Python model (reference)

---

## **Xcode Integration Steps**

### **Step 1: Add New Swift Files to Xcode**
In Xcode Project Navigator:
1. Right-click project → Add Files to Project
2. Select from `/swiftapp/`:
   - `AdModels.swift`
   - `AdDataLoader.swift`
   - `AdPredictor.swift`
   - `AdFraudPredictor.swift`
3. Check "Copy items if needed" ✓
4. Select your target ✓

### **Step 2: Update Project2App.swift**
1. Open `Project2App.swift` in Xcode (the old one)
2. Delete all content
3. Replace with new `Project2App.swift` content (tabbed view)
4. Save (Cmd+S)

### **Step 3: Add CoreML Model to Bundle**
1. In Xcode, right-click Project Navigator → Add Files
2. Select `AdFraudModel.mlmodel` from `/swiftapp/`
3. Check "Copy items if needed" ✓
4. Select your target ✓

### **Step 4: Add CSV Data to Bundle**
1. In Xcode, right-click Project Navigator → Add Files
2. Select `ad_fraud_data_full.csv` from `/swiftapp/`
3. Check "Copy items if needed" ✓
4. Select your target ✓

### **Step 5: Build**
```
Cmd+B
```
Should build cleanly without errors.

### **Step 6: Run**
```
Cmd+R
```
App launches with **two tabs**:
- **Tab 1: "Per-Click"** — Model 1 (existing, click-level)
- **Tab 2: "Per-Ad"** — Model 2 (new, ad-level)

---

## **Expected App Behavior**

### **Tab 1: Per-Click Fraud Detection**
- Loads 100 flagged clicks from Project 1
- Shows: Click ID, timestamp, campaign, publisher
- Tap "Compute Prediction" → Shows on-device CoreML score
- Compare: Project 1 server vs. on-device prediction
- Navigation: Previous/Next through clicks
- ✓ Uses existing `RealTimePredictor` view

### **Tab 2: Per-Ad Campaign Fraud Detection**
- Loads 214 ad campaigns (aggregated from 1M clicks)
- Shows: Ad ID, total clicks, unique IPs, unique devices
- Tap "Analyze Ad Campaign" → Shows on-device CoreML score
- Display: Ad's fraud rate vs. Model 2 prediction
- Navigation: Previous/Next through ads
- ✓ Uses new `AdFraudPredictor` view

---

## **Data Flow Diagram**

```
┌────────────────────────────────────────────────────┐
│           Dual-Model Fraud Detection App            │
├────────────────────────────────────────────────────┤
│                                                    │
│  [Per-Click Tab] ──────→  [Per-Ad Tab]             │
│  (Model 1)              (Model 2)                 │
│  • Clicks               • Ad Campaigns             │
│  • 100 records          • 214 records              │
│  • 11 features          • 19 features              │
│  • FraudModel.mlmodel   • AdFraudModel.mlmodel    │
│  • Real-time            • Batch analysis           │
│                                                    │
│  ┌─────────────────┐    ┌──────────────────┐     │
│  │ RealTimePredictor│    │ AdFraudPredictor  │     │
│  │                 │    │                  │     │
│  │ Show click      │    │ Show ad          │     │
│  │ Predict fraud   │    │ Predict fraud    │     │
│  │ Compare scores  │    │ Compare scores   │     │
│  └─────────────────┘    └──────────────────┘     │
│                                                    │
└────────────────────────────────────────────────────┘
```

---

## **File Structure in Xcode**

After all additions, your Project Navigator should show:

```
Project2App
├── Project2App.swift (UPDATED - tabbed view)
├── AdModels.swift (NEW)
├── AdDataLoader.swift (NEW)
├── AdPredictor.swift (NEW)
├── AdFraudPredictor.swift (NEW)
├── RealTimePredictor.swift (existing)
├── DataLoader.swift (existing)
├── FraudPredictor.swift (existing)
├── FraudModels.swift (existing)
├── AdModels.swift (NEW)
├── FraudModel.mlmodel (existing)
├── AdFraudModel.mlmodel (NEW)
├── flagged_clicks_enhanced.csv (existing)
└── ad_fraud_data_full.csv (NEW)
```

---

## **Testing Checklist**

After building in Xcode:

- [ ] App launches without crashing
- [ ] Tab 1 (Per-Click) loads clicks
- [ ] Tab 1: Can compute predictions
- [ ] Tab 1: Navigate previous/next
- [ ] Switch to Tab 2
- [ ] Tab 2 (Per-Ad) loads ad campaigns
- [ ] Tab 2: Can compute predictions  
- [ ] Tab 2: Navigate previous/next
- [ ] Switch back to Tab 1 — data persisted
- [ ] No console errors

---

## **Performance Expectations**

| Metric | Expected |
|--------|----------|
| App launch time | < 2 seconds |
| Prediction latency (per-click) | < 100ms |
| Prediction latency (per-ad) | < 50ms |
| Memory usage | < 50MB |
| Model load time | < 500ms |

---

## **Next: Phase 6**

After Xcode integration and testing, proceed to:
- Reconciliation & sync system
- Server batch model updates
- Drift monitoring

**Ready to build in Xcode!** 🚀
