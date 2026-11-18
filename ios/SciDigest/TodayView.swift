import SwiftUI

struct TodayView: View {
    @Environment(DigestStore.self) private var store

    var body: some View {
        NavigationStack {
            Group {
                if let digest = store.latest {
                    DigestView(digest: digest)
                } else if store.isLoading {
                    ProgressView("Loading today's research...")
                } else if !store.isConfigured {
                    ContentUnavailableView(
                        "Almost there",
                        systemImage: "link",
                        description: Text("Open the Settings tab and paste your report address, e.g. https://yourname.github.io/scidigest/"))
                } else {
                    ContentUnavailableView {
                        Label("No digest yet", systemImage: "newspaper")
                    } description: {
                        Text(store.errorMessage ?? "Pull down to refresh.")
                    } actions: {
                        Button("Try again") { Task { await store.refresh() } }
                            .buttonStyle(.borderedProminent)
                    }
                }
            }
            .navigationTitle("Today")
            .refreshable { await store.refresh() }
            .task { await store.refresh() }
            .safeAreaInset(edge: .bottom) {
                if let msg = store.errorMessage, store.latest != nil {
                    Text(msg)
                        .font(.footnote)
                        .padding(8)
                        .frame(maxWidth: .infinity)
                        .background(.thinMaterial)
                }
            }
        }
    }
}
