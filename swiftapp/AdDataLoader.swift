import Foundation

/// Loads ad campaign data from CSV file
struct AdDataLoader {
    static func loadFromCSV(filename: String) -> [AdCampaign] {
        guard let bundleURL = Bundle.main.url(forResource: filename, withExtension: "csv") else {
            print("❌ Could not find \(filename).csv in bundle")
            return []
        }

        do {
            let content = try String(contentsOf: bundleURL, encoding: .utf8)
            return parseCSV(content)
        } catch {
            print("❌ Error reading CSV: \(error)")
            return []
        }
    }

    private static func parseCSV(_ content: String) -> [AdCampaign] {
        let lines = content.components(separatedBy: .newlines).filter { !$0.isEmpty }
        guard lines.count > 1 else {
            print("⚠️ CSV is empty or has no data rows")
            return []
        }

        let expectedColumns = [
            "ad_id", "total_clicks", "unique_ips", "unique_devices", "unique_publishers",
            "fraud_clicks", "fraud_rate", "attributed_clicks", "conversion_rate",
            "synthetic_clicks", "synthetic_rate", "ip_concentration", "device_concentration",
            "os_variety", "os_diversity", "unique_timestamps", "timestamp_concentration",
            "unique_ip_device_pairs", "ip_device_ratio", "publishers_per_click"
        ]
        
        // Verify header
        let headerColumns = lines[0].components(separatedBy: ",").map { $0.trimmingCharacters(in: .whitespaces) }
        guard headerColumns.count == expectedColumns.count else {
            print("❌ CSV header mismatch. Expected \(expectedColumns.count) columns, got \(headerColumns.count)")
            return []
        }

        var campaigns: [AdCampaign] = []
        for line in lines.dropFirst() {
            let fields = line.components(separatedBy: ",").map { $0.trimmingCharacters(in: .whitespaces) }
            guard fields.count == expectedColumns.count else { continue }

            // Parse all numeric fields
            guard let adId = Int(fields[0]),
                  let totalClicks = Double(fields[1]),
                  let uniqueIps = Double(fields[2]),
                  let uniqueDevices = Double(fields[3]),
                  let uniquePublishers = Double(fields[4]),
                  let fraudClicks = Double(fields[5]),
                  let fraudRate = Double(fields[6]),
                  let attributedClicks = Double(fields[7]),
                  let conversionRate = Double(fields[8]),
                  let syntheticClicks = Double(fields[9]),
                  let syntheticRate = Double(fields[10]),
                  let ipConcentration = Double(fields[11]),
                  let deviceConcentration = Double(fields[12]),
                  let osVariety = Double(fields[13]),
                  let osDiversity = Double(fields[14]),
                  let uniqueTimestamps = Double(fields[15]),
                  let timestampConcentration = Double(fields[16]),
                  let uniqueIpDevicePairs = Double(fields[17]),
                  let ipDeviceRatio = Double(fields[18]),
                  let publishersPerClick = Double(fields[19]) else {
                continue
            }

            let campaign = AdCampaign(
                id: UUID(),
                adId: adId,
                totalClicks: totalClicks,
                uniqueIps: uniqueIps,
                uniqueDevices: uniqueDevices,
                uniquePublishers: uniquePublishers,
                fraudClicks: fraudClicks,
                fraudRate: fraudRate,
                attributedClicks: attributedClicks,
                conversionRate: conversionRate,
                syntheticClicks: syntheticClicks,
                syntheticRate: syntheticRate,
                ipConcentration: ipConcentration,
                deviceConcentration: deviceConcentration,
                osVariety: osVariety,
                osDiversity: osDiversity,
                uniqueTimestamps: uniqueTimestamps,
                timestampConcentration: timestampConcentration,
                uniqueIpDevicePairs: uniqueIpDevicePairs,
                ipDeviceRatio: ipDeviceRatio,
                publishersPerClick: publishersPerClick
            )
            campaigns.append(campaign)
        }

        print("✅ Loaded \(campaigns.count) ad campaigns from CSV")
        return campaigns
    }
}
