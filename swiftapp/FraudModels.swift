import Foundation

/// A batch of ad clicks flagged for review, with the feature values
/// that fed the fraud model and metadata from Project 1.
struct ClickBatch: Identifiable {
    let id: UUID
    let clickId: String              // Raw click ID from Project 1
    let timestamp: String            // When the click occurred
    let campaignName: String
    let publisherName: String
    let project1Probability: Double  // Original Project 1 server prediction
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
