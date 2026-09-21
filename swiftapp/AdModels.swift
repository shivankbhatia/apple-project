import Foundation

/// An ad campaign with aggregated fraud detection features
struct AdCampaign: Identifiable {
    let id: UUID
    let adId: Int
    let totalClicks: Double
    let uniqueIps: Double
    let uniqueDevices: Double
    let uniquePublishers: Double
    let fraudClicks: Double
    let fraudRate: Double
    let attributedClicks: Double
    let conversionRate: Double
    let syntheticClicks: Double
    let syntheticRate: Double
    let ipConcentration: Double
    let deviceConcentration: Double
    let osVariety: Double
    let osDiversity: Double
    let uniqueTimestamps: Double
    let timestampConcentration: Double
    let uniqueIpDevicePairs: Double
    let ipDeviceRatio: Double
    let publishersPerClick: Double
    
    /// Feature vector in exact order for CoreML model
    var featureVector: [Double] {
        [totalClicks, uniqueIps, uniqueDevices, uniquePublishers,
         fraudClicks, fraudRate, attributedClicks, conversionRate,
         syntheticClicks, syntheticRate, ipConcentration, deviceConcentration,
         osVariety, osDiversity, uniqueTimestamps, timestampConcentration,
         uniqueIpDevicePairs, ipDeviceRatio, publishersPerClick]
    }
    
    /// Campaign name for display (uses ad_id as identifier)
    var displayName: String {
        "Ad \(adId)"
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
