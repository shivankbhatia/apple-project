import Foundation

/// A batch of ad clicks flagged for review, with the feature values
/// that fed the fraud model. Feature order here MUST match FEATURE_NAMES
/// in convert_model.py exactly — that's the contract between the two sides.
struct ClickBatch: Identifiable {
    let id: UUID
    let campaignName: String
    let publisherName: String
    let ipClicks1m: Double
    let ipClicks5m: Double
    let ipClicks1h: Double
    let deviceClicks1m: Double
    let deviceClicks5m: Double
    let deviceClicks1h: Double
    let ipFingerprintEntropy5m: Double
    let ipInterClickGapSeconds: Double
    let clickToInstallDeltaSeconds: Double
    let campaignConversionRate: Double
    let publisherConversionRate: Double

    /// Feature vector in the exact order the model expects.
    var featureVector: [Double] {
        [ipClicks1m, ipClicks5m, ipClicks1h,
         deviceClicks1m, deviceClicks5m, deviceClicks1h,
         ipFingerprintEntropy5m, ipInterClickGapSeconds,
         clickToInstallDeltaSeconds, campaignConversionRate,
         publisherConversionRate]
    }
}

enum RiskLevel: String {
    case low = "Low"
    case medium = "Medium"
    case high = "High"

    static func from(score: Double) -> RiskLevel {
        switch score {
        case ..<0.3: return .low
        case 0.3..<0.7: return .medium
        default: return .high
        }
    }
}

/// Mock data so the UI is testable before you wire in real exported batches
/// from Project 1. Replace `ClickBatch.mockData` with a loader that reads
/// your exported CSV/JSON once Project 1's pipeline output is ready.
extension ClickBatch {
    static let mockData: [ClickBatch] = [
        ClickBatch(
            id: UUID(),
            campaignName: "Summer Sale",
            publisherName: "AdNet A",
            ipClicks1m: 12,
            ipClicks5m: 35,
            ipClicks1h: 120,
            deviceClicks1m: 5,
            deviceClicks5m: 18,
            deviceClicks1h: 60,
            ipFingerprintEntropy5m: 0.82,
            ipInterClickGapSeconds: 3.5,
            clickToInstallDeltaSeconds: 45.0,
            campaignConversionRate: 0.08,
            publisherConversionRate: 0.12
        ),
        ClickBatch(
            id: UUID(),
            campaignName: "App Install Push",
            publisherName: "AdNet B",
            ipClicks1m: 2,
            ipClicks5m: 6,
            ipClicks1h: 25,
            deviceClicks1m: 1,
            deviceClicks5m: 3,
            deviceClicks1h: 12,
            ipFingerprintEntropy5m: 0.15,
            ipInterClickGapSeconds: 120.0,
            clickToInstallDeltaSeconds: 3600.0,
            campaignConversionRate: 0.25,
            publisherConversionRate: 0.30
        ),
        ClickBatch(
            id: UUID(),
            campaignName: "Holiday Promo",
            publisherName: "AdNet C",
            ipClicks1m: 8,
            ipClicks5m: 22,
            ipClicks1h: 85,
            deviceClicks1m: 3,
            deviceClicks5m: 10,
            deviceClicks1h: 40,
            ipFingerprintEntropy5m: 0.55,
            ipInterClickGapSeconds: 25.0,
            clickToInstallDeltaSeconds: 180.0,
            campaignConversionRate: 0.15,
            publisherConversionRate: 0.18
        ),
    ]
}
