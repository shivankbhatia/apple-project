import CoreML
import Foundation

/// Wraps the ad-level CoreML fraud detection model (REGRESSION - predicts fraud_rate)
struct AdPredictor {
    private let model: AdFraudModel

    init() {
        self.model = try! AdFraudModel(configuration: MLModelConfiguration())
    }

    /// Runs inference for one ad campaign entirely on-device.
    /// Returns predicted fraud rate in [0, 1] that matches actual fraud percentage.
    func predict(_ campaign: AdCampaign) -> Double {
        
        let input = AdFraudModelInput(
            total_clicks: campaign.totalClicks,
            unique_ips: campaign.uniqueIps,
            unique_devices: campaign.uniqueDevices,
            unique_publishers: campaign.uniquePublishers,
            fraud_clicks: campaign.fraudClicks,
            attributed_clicks: campaign.attributedClicks,
            conversion_rate: campaign.conversionRate,
            synthetic_clicks: campaign.syntheticClicks,
            synthetic_rate: campaign.syntheticRate,
            ip_concentration: campaign.ipConcentration,
            device_concentration: campaign.deviceConcentration,
            os_variety: campaign.osVariety,
            os_diversity: campaign.osDiversity,
            unique_timestamps: campaign.uniqueTimestamps,
            timestamp_concentration: campaign.timestampConcentration,
            unique_ip_device_pairs: campaign.uniqueIpDevicePairs,
            ip_device_ratio: campaign.ipDeviceRatio,
            publishers_per_click: campaign.publishersPerClick
        )

        guard let output = try? model.prediction(input: input) else {
            print("❌ [Ad \(campaign.adId)] Model prediction failed")
            return 0.0
        }

        // Regression output: target (float32)
        let fraudRate = Double(output.target)
        let clipped = max(0.0, min(1.0, fraudRate))  // Clamp to [0, 1]
        
        print("📊 [Ad \(campaign.adId)] Predicted fraud_rate: \(String(format: "%.4f", clipped))")
        
        return clipped
    }
}
