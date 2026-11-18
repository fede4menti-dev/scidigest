import SwiftUI

struct ArchiveView: View {
    @Environment(DigestStore.self) private var store

    var body: some View {
        NavigationStack {
            Group {
                if let days = store.index?.days, !days.isEmpty {
                    List(days) { day in
                        NavigationLink(value: day) {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(day.displayDate)
                                    .font(.headline)
                                Text("\(day.count) papers · " + day.fields.prefix(4).joined(separator: ", "))
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                ForEach(day.topHeadlines.prefix(2), id: \.self) { h in
                                    Text("• " + h)
                                        .font(.subheadline)
                                        .lineLimit(1)
                                }
                            }
                            .padding(.vertical, 2)
                        }
                    }
                } else {
                    ContentUnavailableView("No past reports yet", systemImage: "calendar",
                                           description: Text("Reports appear here after each daily run."))
                }
            }
            .navigationTitle("Archive")
            .navigationDestination(for: DayEntry.self) { DayLoaderView(date: $0.date) }
            .refreshable { await store.refresh() }
        }
    }
}

private struct DayLoaderView: View {
    @Environment(DigestStore.self) private var store
    let date: String
    @State private var digest: Digest?
    @State private var error: String?

    var body: some View {
        Group {
            if let digest {
                DigestView(digest: digest)
            } else if let error {
                ContentUnavailableView("Couldn't load this day", systemImage: "wifi.exclamationmark",
                                       description: Text(error))
            } else {
                ProgressView()
            }
        }
        .navigationTitle(DayFormat.display(date))
        .navigationBarTitleDisplayMode(.inline)
        .task {
            do { digest = try await store.digest(for: date) }
            catch { self.error = error.localizedDescription }
        }
    }
}
