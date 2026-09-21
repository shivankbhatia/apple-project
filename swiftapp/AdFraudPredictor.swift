import SwiftUI

struct AdFraudPredictor: View {
    @State private var allCampaigns: [AdCampaign] = []
    @State private var currentIndex: Int = 0
    @State private var currentPrediction: Double? = nil
    @State private var isComputing = false
    @State private var isLoading = true
    @State private var errorMessage: String? = nil
    
    private let predictor = AdPredictor()
    
    private var currentCampaign: AdCampaign? {
        guard currentIndex >= 0 && currentIndex < allCampaigns.count else { return nil }
        return allCampaigns[currentIndex]
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
            LinearGradient(
                gradient: Gradient(colors: [
                    Color.purple.opacity(0.1),
                    Color.blue.opacity(0.1)
                ]),
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()
            
            VStack(spacing: 0) {
                // Header
                VStack(alignment: .center, spacing: 8) {
                    Text("Ad Campaign Fraud Detection")
                        .font(.headline)
                        .foregroundStyle(.primary)
                    Text("Model 2: On-Device Ad-Level Analysis")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(Color.white.opacity(0.5))
                
                if isLoading {
                    VStack(spacing: 16) {
                        ProgressView()
                            .scaleEffect(1.5)
                        Text("Loading ad campaigns...")
                            .foregroundStyle(.secondary)
                    }
                    .frame(maxHeight: .infinity)
                } else if let error = errorMessage {
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
                } else if let campaign = currentCampaign {
                    VStack(spacing: 20) {
                        // Ad Info Card
                        VStack(alignment: .leading, spacing: 12) {
                            HStack {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text("Ad ID")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                    Text(String(campaign.adId))
                                        .font(.headline)
                                }
                                Spacer()
                                VStack(alignment: .trailing, spacing: 4) {
                                    Text("Total Clicks")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                    Text(String(format: "%.0f", campaign.totalClicks))
                                        .font(.headline)
                                }
                            }
                            
                            Divider()
                            
                            // Quick stats (3 columns)
                            HStack(spacing: 16) {
                                StatItem(label: "Unique IPs", value: String(format: "%.0f", campaign.uniqueIps))
                                StatItem(label: "Unique Devices", value: String(format: "%.0f", campaign.uniqueDevices))
                                StatItem(label: "Conv Rate", value: String(format: "%.1f%%", campaign.conversionRate * 100))
                            }
                        }
                        .padding()
                        .background(Color.white)
                        .cornerRadius(12)
                        .shadow(radius: 2)
                        
                        // Prediction Card
                        VStack(spacing: 16) {
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Ad Fraud Analysis")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                
                                HStack {
                                    Text(String(format: "%.1f%%", campaign.fraudRate * 100))
                                        .font(.system(.body, design: .monospaced))
                                        .fontWeight(.semibold)
                                    Text("fraud in clicks")
                                        .font(.caption)
                                    Spacer()
                                    Text(String(format: "%.0f", campaign.fraudClicks) + " flagged")
                                        .font(.caption)
                                }
                                
                                GeometryReader { geometry in
                                    ZStack(alignment: .leading) {
                                        RoundedRectangle(cornerRadius: 4)
                                            .fill(Color.gray.opacity(0.2))
                                        
                                        RoundedRectangle(cornerRadius: 4)
                                            .fill(campaign.fraudRate > 0.5 ? Color.red : Color.orange)
                                            .frame(width: geometry.size.width * campaign.fraudRate)
                                    }
                                }
                                .frame(height: 6)
                            }
                            .padding()
                            .background(Color.white)
                            .cornerRadius(10)
                            
                            // On-Device Prediction
                            if let prediction = currentPrediction {
                                VStack(alignment: .leading, spacing: 8) {
                                    Text("On-Device Model Prediction")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                    
                                    HStack {
                                        Text(String(format: "%.1f%%", prediction * 100))
                                            .font(.system(.body, design: .monospaced))
                                            .fontWeight(.semibold)
                                        
                                        Spacer()
                                        
                                        Text(isFlagged ? "🚨 FRAUD" : "✅ CLEAN")
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
                            } else if isComputing {
                                VStack(spacing: 12) {
                                    ProgressView()
                                        .scaleEffect(1.3)
                                    Text("Running CoreML model...")
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
                                            Text("Analyze Ad Campaign")
                                        }
                                        .frame(maxWidth: .infinity)
                                        .padding()
                                        .background(Color.purple)
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
                        
                        // Navigation
                        VStack(spacing: 12) {
                            Text("Campaign \(currentIndex + 1) of \(allCampaigns.count)")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            
                            HStack(spacing: 12) {
                                Button(action: previousCampaign) {
                                    Image(systemName: "chevron.left.circle.fill")
                                        .font(.system(size: 32))
                                        .foregroundStyle(.purple)
                                }
                                .disabled(currentIndex == 0)
                                .opacity(currentIndex == 0 ? 0.3 : 1.0)
                                
                                Spacer()
                                
                                Button(action: nextCampaign) {
                                    Image(systemName: "chevron.right.circle.fill")
                                        .font(.system(size: 32))
                                        .foregroundStyle(.purple)
                                }
                                .disabled(currentIndex == allCampaigns.count - 1)
                                .opacity(currentIndex == allCampaigns.count - 1 ? 0.3 : 1.0)
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
            loadCampaigns()
        }
    }
    
    private func loadCampaigns() {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            let loaded = AdDataLoader.loadFromCSV(filename: "ad_fraud_data_full")
            
            if loaded.isEmpty {
                self.errorMessage = "Could not load ads. Is ad_fraud_data_full.csv in the bundle?"
            } else {
                self.allCampaigns = loaded
                self.currentIndex = 0
                self.currentPrediction = nil
            }
            self.isLoading = false
        }
    }
    
    private func computePrediction() {
        guard let campaign = currentCampaign else { return }
        
        isComputing = true
        
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
            self.currentPrediction = self.predictor.predict(campaign)
            self.isComputing = false
        }
    }
    
    private func nextCampaign() {
        if currentIndex < allCampaigns.count - 1 {
            currentIndex += 1
            currentPrediction = nil
        }
    }
    
    private func previousCampaign() {
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
    AdFraudPredictor()
}
