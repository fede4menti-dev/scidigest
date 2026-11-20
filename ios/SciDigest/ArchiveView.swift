import SwiftUI

struct ArchiveView: View {
    enum Kind: String, CaseIterable, Identifiable {
        case daily = "Daily", weekly = "Weekly", monthly = "Monthly"
        var id: String { rawValue }
    }

    @Environment(DigestStore.self) private var store
    @State private var kind: Kind = .daily

    var body: some View {
        NavigationStack {
            List {
                Picker("Report type", selection: $kind) {
                    ForEach(Kind.allCases) { Text($0.rawValue).tag($0) }
                }
                .pickerStyle(.segmented)
                .listRowBackground(Color.clear)
                .listRowInsets(EdgeInsets())

                switch kind {
                case .daily:
                    let days = store.index?.days ?? []
                    if days.isEmpty { empty("No daily digests yet", "They appear here after each morning's run.") }
                    ForEach(days) { day in
                        NavigationLink(value: day) { DayRow(day: day) }
                    }
                case .weekly:
                    let items = store.index?.weekly ?? []
                    if items.isEmpty { empty("No weekly reviews yet", "A weekly review is published every Sunday.") }
                    ForEach(items) { r in NavigationLink(value: r) { ReviewRow(review: r) } }
                case .monthly:
                    let items = store.index?.monthly ?? []
                    if items.isEmpty { empty("No monthly reviews yet", "A monthly review is published on the 1st of each month.") }
                    ForEach(items) { r in NavigationLink(value: r) { ReviewRow(review: r) } }
                }
            }
            .navigationTitle("Archive")
            .navigationDestination(for: DayEntry.self) {
                DigestLoaderView(name: $0.date, title: DayFormat.short($0.date))
            }
            .navigationDestination(for: ReviewEntry.self) { DigestLoaderView(name: $0.id, title: $0.badge) }
            .navigationDestination(for: Paper.self) { PaperDetailView(paper: $0) }
            .refreshable { await store.refresh() }
        }
    }

    private func empty(_ title: String, _ detail: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title).font(.headline)
            Text(detail).font(.subheadline).foregroundStyle(.secondary)
        }
        .padding(.vertical, 8)
    }
}

private struct DayRow: View {
    let day: DayEntry

    var body: some View {
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
