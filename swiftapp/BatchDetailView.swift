import SwiftUI

struct BatchDetailView: View {
    let batch: ClickBatch
    let score: Double
    let risk: RiskLevel

    private var featureRows: [(label: String, value: String)] {
        [
            ("Click velocity", String(format: "%.2f", batch.clickVelocity)),
            ("Fingerprint entropy", String(format: "%.2f", batch.fingerprintEntropy)),
            ("Click-to-conversion ratio", String(format: "%.2f", batch.clickToConvRatio)),
            ("Geo mismatch", batch.geoMismatch == 1.0 ? "Yes" : "No"),
            ("Time to click", "\(Int(batch.timeToClickMs)) ms"),
            ("IP reuse rate", String(format: "%.2f", batch.ipReuseRate)),
        ]
    }

    var body: some View {
        Form {
            Section("Summary") {
                LabeledContent("Campaign", value: batch.campaignName)
                LabeledContent("Publisher", value: batch.publisherName)
                LabeledContent("Fraud score", value: String(format: "%.1f%%", score * 100))
                LabeledContent("Risk level", value: risk.rawValue)
            }

            Section("Features") {
                ForEach(featureRows, id: \.label) { row in
                    LabeledContent(row.label, value: row.value)
                }
            }

            Section {
                Text("Inference runs fully on-device via CoreML — no data leaves this device for scoring.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .navigationTitle(batch.campaignName)
    }
}

#Preview {
    NavigationStack {
        BatchDetailView(batch: ClickBatch.mockData[0], score: 0.87, risk: .high)
    }
}
