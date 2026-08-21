/**
 * ArciTEK.AI iOS Application
 * "Every build is a work of art" - infinite♾2025
 *
 * Quantum-Enhanced AI Development Platform - iOS Companion
 * Minimum iOS: 16.0
 * Framework: SwiftUI
 */

import SwiftUI
import WebKit

// MARK: - App Entry Point

@main
struct ArciTEKApp: App {
    @StateObject private var appState = AppState()
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(appState)
                .preferredColorScheme(.dark)
        }
    }
}

// MARK: - App State

class AppState: ObservableObject {
    @Published var isSetupComplete: Bool = UserDefaults.standard.bool(forKey: "setupComplete")
    @Published var serverURL: String = UserDefaults.standard.string(forKey: "serverURL") ?? ""
    @Published var isConnected: Bool = false
    
    func completeSetup(url: String) {
        serverURL = url
        isSetupComplete = true
        UserDefaults.standard.set(true, forKey: "setupComplete")
        UserDefaults.standard.set(url, forKey: "serverURL")
    }
}

// MARK: - Content View

struct ContentView: View {
    @EnvironmentObject var appState: AppState
    @State private var showSplash = true
    
    var body: some View {
        ZStack {
            if showSplash {
                SplashView()
                    .onAppear {
                        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                            withAnimation { showSplash = false }
                        }
                    }
            } else if !appState.isSetupComplete {
                SetupWizardView()
            } else {
                MainDashboardView()
            }
        }
    }
}

// MARK: - Splash Screen

struct SplashView: View {
    @State private var opacity: Double = 0
    @State private var scale: CGFloat = 0.8
    
    var body: some View {
        ZStack {
            LinearGradient(
                colors: [Color(hex: "1A1A2E"), Color(hex: "16213E"), Color(hex: "0F3460")],
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()
            
            VStack(spacing: 16) {
                Text("ArciTEK.AI")
                    .font(.system(size: 42, weight: .bold))
                    .foregroundColor(Color(hex: "4A9EFF"))
                
                Text("Quantum-Enhanced AI Development Platform")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.7))
                
                ProgressView()
                    .tint(Color(hex: "4A9EFF"))
                    .padding(.top, 32)
                
                Spacer().frame(height: 48)
                
                Text("\"Every build is a work of art\"")
                    .font(.caption2)
                    .italic()
                    .foregroundColor(.white.opacity(0.5))
                
                Text("infinite♾2025")
                    .font(.caption2)
                    .foregroundColor(Color(hex: "4A9EFF").opacity(0.7))
            }
            .scaleEffect(scale)
            .opacity(opacity)
        }
        .onAppear {
            withAnimation(.easeOut(duration: 0.8)) {
                opacity = 1
                scale = 1
            }
        }
    }
}

// MARK: - Setup Wizard

struct SetupWizardView: View {
    @EnvironmentObject var appState: AppState
    @State private var currentStep = 0
    @State private var serverURL = ""
    @State private var apiKey = ""
    @State private var autoConnect = true
    
    let steps = ["Welcome", "Connect", "API Keys", "Complete"]
    
    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                // Progress bar
                ProgressView(value: Double(currentStep + 1), total: Double(steps.count))
                    .tint(Color(hex: "4A9EFF"))
                    .padding(.horizontal)
                
                Text("Step \(currentStep + 1) of \(steps.count): \(steps[currentStep])")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .padding(.top, 8)
                
                // Content
                ScrollView {
                    VStack(spacing: 24) {
                        switch currentStep {
                        case 0: welcomeContent
                        case 1: connectContent
                        case 2: apiKeyContent
                        case 3: completeContent
                        default: EmptyView()
                        }
                    }
                    .padding(24)
                }
                
                // Navigation
                HStack {
                    if currentStep > 0 {
                        Button("Back") { currentStep -= 1 }
                            .buttonStyle(.bordered)
                    }
                    
                    Spacer()
                    
                    Button(currentStep < steps.count - 1 ? "Next" : "Get Started") {
                        if currentStep < steps.count - 1 {
                            currentStep += 1
                        } else {
                            appState.completeSetup(url: serverURL.isEmpty ? "http://localhost:8000" : serverURL)
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(Color(hex: "4A9EFF"))
                }
                .padding(24)
            }
            .background(Color(hex: "1A1A2E"))
            .navigationTitle("ArciTEK.AI Setup")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
    
    var welcomeContent: some View {
        VStack(spacing: 24) {
            Image(systemName: "sparkles")
                .font(.system(size: 60))
                .foregroundColor(Color(hex: "4A9EFF"))
            
            Text("Welcome to ArciTEK.AI")
                .font(.title)
                .fontWeight(.bold)
            
            Text("This mobile companion connects to your ArciTEK.AI server, giving you access to quantum computing, AI models, and development tools from anywhere.")
                .multilineTextAlignment(.center)
                .foregroundColor(.secondary)
            
            VStack(spacing: 8) {
                FeatureRow(icon: "atom", title: "5 Quantum Platforms", subtitle: "IBM, IonQ, Google, Braket, Azure")
                FeatureRow(icon: "brain", title: "325B AI Parameters", subtitle: "SupersynapAI, Argo, Chimera")
                FeatureRow(icon: "checkmark.seal.fill", title: "99.97% Precision", subtitle: "Quantum Perfect builds")
                FeatureRow(icon: "bolt.fill", title: "+26.7% Quantum Boost", subtitle: "Performance enhancement")
            }
        }
    }
    
    var connectContent: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Connect to Server")
                .font(.title2)
                .fontWeight(.bold)
            
            Text("Enter the URL of your ArciTEK.AI server:")
                .foregroundColor(.secondary)
            
            TextField("http://localhost:8000", text: $serverURL)
                .textFieldStyle(.roundedBorder)
                .autocapitalization(.none)
                .disableAutocorrection(true)
            
            Toggle("Auto-connect on launch", isOn: $autoConnect)
            
            Text("Tip: Use your computer's IP address if on the same network (e.g., http://192.168.1.100:8000)")
                .font(.caption)
                .foregroundColor(.secondary)
                .padding()
                .background(Color(hex: "16213E"))
                .cornerRadius(8)
        }
    }
    
    var apiKeyContent: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("API Configuration")
                .font(.title2)
                .fontWeight(.bold)
            
            Text("Optionally configure API keys for direct mobile access:")
                .foregroundColor(.secondary)
            
            SecureField("OpenAI API Key (optional)", text: $apiKey)
                .textFieldStyle(.roundedBorder)
            
            Text("You can skip this step and configure API keys later through the server's configuration wizard.")
                .font(.caption)
                .foregroundColor(.secondary)
                .padding()
                .background(Color(hex: "16213E"))
                .cornerRadius(8)
        }
    }
    
    var completeContent: some View {
        VStack(spacing: 24) {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 80))
                .foregroundColor(.green)
            
            Text("Setup Complete!")
                .font(.title)
                .fontWeight(.bold)
            
            Text("ArciTEK.AI is ready to use. Tap 'Get Started' to open the dashboard.")
                .multilineTextAlignment(.center)
                .foregroundColor(.secondary)
        }
    }
}

struct FeatureRow: View {
    let icon: String
    let title: String
    let subtitle: String
    
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .foregroundColor(Color(hex: "4A9EFF"))
                .frame(width: 24)
            
            VStack(alignment: .leading) {
                Text(title).fontWeight(.medium)
                Text(subtitle).font(.caption).foregroundColor(.secondary)
            }
            
            Spacer()
        }
        .padding(12)
        .background(Color(hex: "16213E"))
        .cornerRadius(8)
    }
}

// MARK: - Main Dashboard

struct MainDashboardView: View {
    @EnvironmentObject var appState: AppState
    
    var body: some View {
        WebViewContainer(url: appState.serverURL)
            .ignoresSafeArea(edges: .bottom)
    }
}

struct WebViewContainer: UIViewRepresentable {
    let url: String
    
    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.allowsInlineMediaPlayback = true
        
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.isOpaque = false
        webView.backgroundColor = UIColor(Color(hex: "1A1A2E"))
        
        if let url = URL(string: url) {
            webView.load(URLRequest(url: url))
        }
        
        return webView
    }
    
    func updateUIView(_ webView: WKWebView, context: Context) {}
}

// MARK: - Color Extension

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 6:
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (255, 0, 0, 0)
        }
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue: Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}
