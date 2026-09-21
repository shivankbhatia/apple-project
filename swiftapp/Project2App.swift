import SwiftUI

@main
struct Project2App: App {
    var body: some Scene {
        WindowGroup {
            DualModelView()
        }
    }
}

struct DualModelView: View {
    @State private var selectedTab = 0
    
    var body: some View {
        TabView(selection: $selectedTab) {
            // Tab 1: Per-Click Fraud Detection (Model 1)
            RealTimePredictor()
                .tabItem {
                    Label("Per-Click", systemImage: "1.circle.fill")
                }
                .tag(0)
            
            // Tab 2: Per-Ad Fraud Detection (Model 2)
            AdFraudPredictor()
                .tabItem {
                    Label("Per-Ad", systemImage: "2.circle.fill")
                }
                .tag(1)
        }
    }
}

#Preview {
    DualModelView()
}
