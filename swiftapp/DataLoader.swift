import Foundation

/// Loads click batch data from a CSV file exported from Project 1.
struct DataLoader {
    static func loadFromCSV(filename: String) -> [ClickBatch] {
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

    private static func parseCSV(_ content: String) -> [ClickBatch] {
        let lines = content.components(separatedBy: .newlines).filter { !$0.isEmpty }
        guard lines.count > 1 else {
            print("⚠️ CSV is empty or has no data rows")
            return []
        }

        let expectedColumns = [
            "click_id", "timestamp", "campaign_id", "publisher_id", "is_fraud", 
            "project1_fraud_probability",
            "ip_clicks_1m", "ip_clicks_5m", "ip_clicks_1h", 
            "device_clicks_1m", "device_clicks_5m", "device_clicks_1h",
            "ip_fingerprint_entropy_5m", "ip_inter_click_gap_seconds",
            "click_to_install_delta_seconds", "campaign_conversion_rate", 
            "publisher_conversion_rate"
        ]
        
        // Verify header
        let headerColumns = lines[0].components(separatedBy: ",").map { $0.trimmingCharacters(in: .whitespaces) }
        guard headerColumns.count == expectedColumns.count else {
            print("❌ CSV header mismatch")
            return []
        }

        var batches: [ClickBatch] = []
        for line in lines.dropFirst() {
            let fields = line.components(separatedBy: ",").map { $0.trimmingCharacters(in: .whitespaces) }
            guard fields.count == expectedColumns.count else { continue }

            // Parse all numeric fields
            guard let project1Prob = Double(fields[5]),
                  let ipClicks1m = Double(fields[6]),
                  let ipClicks5m = Double(fields[7]),
                  let ipClicks1h = Double(fields[8]),
                  let deviceClicks1m = Double(fields[9]),
                  let deviceClicks5m = Double(fields[10]),
                  let deviceClicks1h = Double(fields[11]),
                  let ipFingerprintEntropy5m = Double(fields[12]),
                  let ipInterClickGapSeconds = Double(fields[13]),
                  let clickToInstallDeltaSeconds = Double(fields[14]),
                  let campaignConversionRate = Double(fields[15]),
                  let publisherConversionRate = Double(fields[16]) else {
                continue
            }

            let batch = ClickBatch(
                id: UUID(),
                clickId: fields[0],
                timestamp: fields[1],
                campaignName: fields[2],
                publisherName: fields[3],
                project1Probability: project1Prob,
                ipClicks1m: ipClicks1m,
                ipClicks5m: ipClicks5m,
                ipClicks1h: ipClicks1h,
                deviceClicks1m: deviceClicks1m,
                deviceClicks5m: deviceClicks5m,
                deviceClicks1h: deviceClicks1h,
                ipFingerprintEntropy5m: ipFingerprintEntropy5m,
                ipInterClickGapSeconds: ipInterClickGapSeconds,
                clickToInstallDeltaSeconds: clickToInstallDeltaSeconds,
                campaignConversionRate: campaignConversionRate,
                publisherConversionRate: publisherConversionRate
            )
            batches.append(batch)
        }

        print("✅ Loaded \(batches.count) click batches from CSV")
        return batches
    }
}
