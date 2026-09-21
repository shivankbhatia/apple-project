import SwiftUI

struct RealTimePredictor: View {
    @State private var allBatches: [ClickBatch] = []
    @State private var currentIndex: Int = 0
    @State private var currentPrediction: Double? = nil
    @State private var isComputing = false
    @State private var isLoading = true
    @State private var errorMessage: String? = nil
    
    private let predictor = FraudPredictor()
    
    private var currentBatch: ClickBatch? {
        guard currentIndex >= 0 && currentIndex < allBatches.count else { return nil }
        return allBatches[currentIndex]
    }
    
    private var currentRisk: RiskLevel? {
        guard let prediction = currentPrediction else { return nil }
        return RiskLevel.from(score: prediction)
    }
    
    private var isFlagged: Bool {
        guard let risk = currentRisk else { return false }
        return risk == .high
    }
    
    var body: some View {
        ZStack {
            // Background gradient
            LinearGradient(
                gradient: Gradient(colors: [
                    Color.blue.opacity(0.1),
                    Color.purple.opacity(0.1)
                ]),
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()
            
            VStack(spacing: 0) {
                // Header
                VStack(alignment: .center, spacing: 8) {
                    Text("Real-Time Ad Fraud Detection")
                        .font(.headline)
                        .foregroundStyle(.primary)
                    Text("On-Device ML from Project 1 Data")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(Color.white.opacity(0.5))
                
                if isLoading {
                    // Loading state
                    VStack(spacing: 16) {
                        ProgressView()
                            .scaleEffect(1.5)
                        Text("Loading real clicks from Project 1...")
                            .foregroundStyle(.secondary)
                    }
                    .frame(maxHeight: .infinity)
                } else if let error = errorMessage {
                    // Error state
                    VStack(spacing: 12) {
                        Image(systemName: "exclamationmark.triangle")
                            .font(.system(size: 48))
                            .foregroundStyle(.red)
                        Text("Error")
                            .font(.headline)
                        Text(error)
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .frame(maxHeight: .infinity)
                    .padding()
                } else if let batch = currentBatch {
                    // Main content
                    VStack(spacing: 20) {
                        // Metadata Section
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text("Click ID")
                                        .font(.caption2)
                                        .foregroundStyle(.secondary)
                                    Text(batch.clickId.prefix(16) + "...")
                                        .font(.caption)
                                        .monospaced()
                                }
                                Spacer()
                                VStack(alignment: .trailing, spacing: 2) {
                                    Text("Timestamp")
                                        .font(.caption2)
                                        .foregroundStyle(.secondary)
                                    Text(batch.timestamp)
                                        .font(.caption)
                                }
                            }
                        }
                        .padding()
                        .background(Color.gray.opacity(0.1))
                        .cornerRadius(8)
                        
                        // Ad Info Card
                        VStack(alignment: .leading, spacing: 12) {
                            HStack {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text("Campaign")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                    Text(batch.campaignName)
                                        .font(.headline)
                                }
                                Spacer()
                                VStack(alignment: .trailing, spacing: 4) {
                                    Text("Publisher")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                    Text(batch.publisherName)
                                        .font(.headline)
                                }
                            }
                            
                            Divider()
                            
                            // Quick stats
                            HStack(spacing: 16) {
                                StatItem(label: "IP Clicks (1m)", value: String(format: "%.0f", batch.ipClicks1m))
                                StatItem(label: "Device Clicks", value: String(format: "%.0f", batch.deviceClicks1m))
                                StatItem(label: "Conv Rate", value: String(format: "%.1f%%", batch.campaignConversionRate * 100))
                            }
                        }
                        .padding()
                        .background(Color.white)
                        .cornerRadius(12)
                        .shadow(radius: 2)
                        
                        // Prediction Comparison Card
                        VStack(spacing: 16) {
                            // Project 1 Server Prediction
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Project 1 Server Prediction")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                
                                HStack {
                                    Text(String(format: "%.1f%%", batch.project1Probability * 100))
                                        .font(.system(.body, design: .monospaced))
                                        .fontWeight(.semibold)
                                    
                                    Spacer()
                                    
                                    Text(batch.project1Probability > 0.7 ? "🚨 FLAG" : "✅ PASS")
                                        .font(.caption)
                                        .fontWeight(.semibold)
                                }
                                
                                GeometryReader { geometry in
                                    ZStack(alignment: .leading) {
                                        RoundedRectangle(cornerRadius: 4)
                                            .fill(Color.gray.opacity(0.2))
                                        
                                        RoundedRectangle(cornerRadius: 4)
                                            .fill(batch.project1Probability > 0.7 ? Color.red : Color.green)
                                            .frame(width: geometry.size.width * batch.project1Probability)
                                    }
                                }
                                .frame(height: 6)
                            }
                            .padding()
                            .background(Color.white)
                            .cornerRadius(10)
                            
                            Divider()
                                .padding(.vertical, 4)
                            
                            // On-Device Prediction
                            if let prediction = currentPrediction {
                                VStack(alignment: .leading, spacing: 8) {
                                    Text("On-Device Prediction (CoreML)")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                    
                                    HStack {
                                        Text(String(format: "%.1f%%", prediction * 100))
                                            .font(.system(.body, design: .monospaced))
                                            .fontWeight(.semibold)
                                        
                                        Spacer()
                                        
                                        Text(isFlagged ? "🚨 FLAG" : "✅ PASS")
                                            .font(.caption)
                                            .fontWeight(.semibold)
                                    }
                                    
                                    GeometryReader { geometry in
                                        ZStack(alignment: .leading) {
                                            RoundedRectangle(cornerRadius: 4)
                                                .fill(Color.gray.opacity(0.2))
                                            
                                            RoundedRectangle(cornerRadius: 4)
                                                .fill(isFlagged ? Color.red : Color.green)
                                                .frame(width: geometry.size.width * prediction)
                                        }
                                    }
                                    .frame(height: 6)
                                }
                                .padding()
                                .background(Color.white)
                                .cornerRadius(10)
                                
                                // Parity Check
                                let diff = abs(prediction - batch.project1Probability)
                                VStack(alignment: .leading, spacing: 4) {
                                    HStack {
                                        Image(systemName: diff < 0.05 ? "checkmark.circle.fill" : "exclamationmark.circle.fill")
                                            .foregroundStyle(diff < 0.05 ? Color.green : Color.orange)
                                        
                                        Text("Parity Check")
                                            .font(.caption)
                                            .fontWeight(.semibold)
                                        
                                        Spacer()
                                        
                                        Text(String(format: "Δ %.1f%%", diff * 100))
                                            .font(.caption2)
                                            .monospaced()
                                    }
                                }
                                .padding(.horizontal, 8)
                                .padding(.vertical, 6)
                                .background(Color.blue.opacity(0.1))
                                .cornerRadius(8)
                                
                            } else if isComputing {
                                VStack(spacing: 12) {
                                    ProgressView()
                                        .scaleEffect(1.3)
                                    Text("Running CoreML inference...")
                                        .foregroundStyle(.secondary)
                                        .font(.subheadline)
                                }
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(Color.white)
                                .cornerRadius(12)
                            } else {
                                VStack(spacing: 12) {
                                    Button(action: computePrediction) {
                                        HStack {
                                            Image(systemName: "sparkles")
                                            Text("Compute On-Device")
                                        }
                                        .frame(maxWidth: .infinity)
                                        .padding()
                                        .background(Color.blue)
                                        .foregroundStyle(.white)
                                        .cornerRadius(8)
                                    }
                                }
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(Color.white)
                                .cornerRadius(12)
                            }
                        }
                        .padding()
                        .background(Color.white.opacity(0.7))
                        .cornerRadius(12)
                        .shadow(radius: 2)
                        
                        Spacer()
                        
                        // Navigation and info
                        VStack(spacing: 12) {
                            Text("Ad \(currentIndex + 1) of \(allBatches.count)")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            
                            HStack(spacing: 12) {
                                Button(action: previousBatch) {
                                    Image(systemName: "chevron.left.circle.fill")
                                        .font(.system(size: 32))
                                        .foregroundStyle(.blue)
                                }
                                .disabled(currentIndex == 0)
                                .opacity(currentIndex == 0 ? 0.3 : 1.0)
                                
                                Spacer()
                                
                                Button(action: nextBatch) {
                                    Image(systemName: "chevron.right.circle.fill")
                                        .font(.system(size: 32))
                                        .foregroundStyle(.blue)
                                }
                                .disabled(currentIndex == allBatches.count - 1)
                                .opacity(currentIndex == allBatches.count - 1 ? 0.3 : 1.0)
                            }
                        }
                    }
                    .padding()
                } else {
                    Text("No ads to display")
                        .foregroundStyle(.secondary)
                        .frame(maxHeight: .infinity)
                }
            }
        }
        .onAppear {
            loadAds()
        }
    }
    
    private func loadAds() {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            let loaded = DataLoader.loadFromCSV(filename: "flagged_clicks_enhanced")
            
            if loaded.isEmpty {
                self.errorMessage = "Could not load ads. Is flagged_clicks_enhanced.csv in the bundle?"
            } else {
                self.allBatches = loaded
                self.currentIndex = 0
                self.currentPrediction = nil
            }
            self.isLoading = false
        }
    }
    
    private func computePrediction() {
        guard let batch = currentBatch else { return }
        
        isComputing = true
        
        // Simulate computation delay for visual feedback
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
            self.currentPrediction = self.predictor.predict(batch)
            self.isComputing = false
        }
    }
    
    private func nextBatch() {
        if currentIndex < allBatches.count - 1 {
            currentIndex += 1
            currentPrediction = nil
        }
    }
    
    private func previousBatch() {
        if currentIndex > 0 {
            currentIndex -= 1
            currentPrediction = nil
        }
    }
}

struct StatItem: View {
    let label: String
    let value: String
    
    var body: some View {
        VStack(alignment: .center, spacing: 4) {
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.subheadline)
                .fontWeight(.semibold)
        }
        .frame(maxWidth: .infinity)
    }
}

#Preview {
    RealTimePredictor()
}
