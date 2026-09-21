import SwiftUI

struct ContentView: View {
    private let predictor = FraudPredictor()
    @State private var batches: [ClickBatch] = ClickBatch.mockData

    /// (batch, score, risk) computed once per batch — avoids re-running
    /// inference every time SwiftUI redraws the list.
    private var scoredBatches: [(batch: ClickBatch, score: Double, risk: RiskLevel)] {
        batches.map { batch in
            let score = predictor.predict(batch)
            return (batch, score, RiskLevel.from(score: score))
        }
        .sorted { $0.score > $1.score } // highest risk first
    }

    var body: some View {
        NavigationStack {
            List(scoredBatches, id: \.batch.id) { item in
                NavigationLink {
                    BatchDetailView(batch: item.batch, score: item.score, risk: item.risk)
                } label: {
                    HStack {
                        VStack(alignment: .leading) {
                            Text(item.batch.campaignName)
                                .font(.headline)
                            Text(item.batch.publisherName)
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }
                        Spacer()
                        RiskBadge(risk: item.risk, score: item.score)
                    }
                    .padding(.vertical, 4)
                }
            }
            .navigationTitle("Flagged Clicks")
        }
    }
}

struct RiskBadge: View {
    let risk: RiskLevel
    let score: Double

    private var color: Color {
        switch risk {
        case .low: return .green
        case .medium: return .orange
        case .high: return .red
        }
    }

    var body: some View {
        VStack(alignment: .trailing, spacing: 2) {
            Text(risk.rawValue)
                .font(.caption).bold()
                .foregroundStyle(color)
            Text(String(format: "%.0f%%", score * 100))
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 8).padding(.vertical, 4)
        .background(color.opacity(0.12))
        .clipShape(Capsule())
    }
}

#Preview {
    ContentView()
}
