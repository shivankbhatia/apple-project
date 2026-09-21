import SwiftUI

struct ContentView: View {
    private let predictor = FraudPredictor()
    @State private var batches: [ClickBatch] = []
    @State private var isLoading = true
    @State private var errorMessage: String? = nil

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
            Group {
                if isLoading {
                    VStack {
                        ProgressView()
                        Text("Loading real click data...")
                            .foregroundStyle(.secondary)
                            .padding(.top)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if let error = errorMessage {
                    VStack(spacing: 12) {
                        Image(systemName: "exclamationmark.triangle")
                            .font(.largeTitle)
                            .foregroundStyle(.red)
                        Text("Error Loading Data")
                            .font(.headline)
                        Text(error)
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding()
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if scoredBatches.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "checkmark.circle")
                            .font(.largeTitle)
                            .foregroundStyle(.green)
                        Text("No Flagged Clicks")
                            .font(.headline)
                        Text("No fraud detected in this batch.")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
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
                }
            }
            .navigationTitle("Flagged Clicks")
        }
        .onAppear {
            loadRealData()
        }
    }

    private func loadRealData() {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            let loadedBatches = DataLoader.loadFromCSV(filename: "flagged_clicks")
            
            if loadedBatches.isEmpty {
                self.errorMessage = "Could not load flagged clicks. Is flagged_clicks.csv in the bundle?"
            } else {
                self.batches = loadedBatches
            }
            self.isLoading = false
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
