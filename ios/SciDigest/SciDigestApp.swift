import SwiftUI

@main
struct SciDigestApp: App {
    @State private var store = DigestStore()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(store)
        }
    }
}

struct RootView: View {
    var body: some View {
        TabView {
            TodayView()
                .tabItem { Label("Today", systemImage: "sparkles") }
            ArchiveView()
                .tabItem { Label("Archive", systemImage: "calendar") }
            SettingsView()
                .tabItem { Label("Settings", systemImage: "gearshape") }
        }
    }
}
