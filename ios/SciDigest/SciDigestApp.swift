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
    @AppStorage(TopicPrefs.onboardedKey) private var didChooseTopics = false

    var body: some View {
        TabView {
            TodayView()
                .tabItem { Label("Today", systemImage: "sparkles") }
            ArchiveView()
                .tabItem { Label("Archive", systemImage: "calendar") }
            IdeaCheckView()
                .tabItem { Label("Idea Check", systemImage: "lightbulb") }
            SettingsView()
                .tabItem { Label("Settings", systemImage: "gearshape") }
        }
        .tint(Theme.accent)
        .sheet(isPresented: Binding(get: { !didChooseTopics }, set: { if !$0 { didChooseTopics = true } })) {
            NavigationStack {
                TopicsView { didChooseTopics = true }
                    .toolbar {
                        ToolbarItem(placement: .cancellationAction) {
                            Button("Skip") { didChooseTopics = true }
                        }
                    }
            }
            .tint(Theme.accent)
            .interactiveDismissDisabled()
        }
    }
}
