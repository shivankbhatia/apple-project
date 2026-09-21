import SwiftUI

struct BatchDetailView: View {
    let batch: ClickBatch
    let score: Double
    let risk: RiskLevel

    private var featureRows: [(label: String, value: String)] {
        [
            ("IP clicks (1m)", String(format: "%.0f", batch.ipClicks1m)),
            ("IP clicks (5m)", String(format: "%.0f", batch.ipClicks5m)),
            ("IP clicks (1h)", String(format: "%.0f", batch.ipClicks1h)),
            ("Device clicks (1m)", String(format: "%.0f", batch.deviceClicks1m)),
            ("Device clicks (5m)", String(format: "%.0f", batch.deviceClicks5m)),
            ("Device clicks (1h)", String(format: "%.0f", batch.deviceClicks1h)),
            ("IP fingerprint entropy", String(format: "%.2f", batch.ipFingerprintEntropy5m)),
            ("IP inter-click gap", String(format: "%.1f", batch.ipInterClickGapSeconds) + "s"),
            ("Click-to-install delta", String(format: "%.0f", batch.clickToInstallDeltaSeconds) + "s"),
            ("Campaign conversion rate", String(format: "%.1f%%", batch.campaignConversionRate * 100)),
            ("Publisher conversion rate", String(format: "%.1f%%", batch.publisherConversionRate * 100)),
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
