import SwiftUI

/// Choose which research topics to follow. Used on first launch and from Settings.
struct TopicsView: View {
    var onFinish: (() -> Void)? = nil

    @Environment(DigestStore.self) private var store
    @AppStorage(TopicPrefs.key) private var followedRaw = ""
    @State private var draft: Set<String> = []
    @State private var loaded = false
    @State private var saving = false
    @State private var resultMessage: String?

    var body: some View {
        List {
            Section {
                Text("Pick the fields you want to read about. Your daily papers and weekly and monthly reviews will show these first.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                Button {
                    draft = []
                } label: {
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("All topics")
                            Text("The editor's picks across every field")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        Spacer()
                        checkmark(draft.isEmpty)
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
            }

            ForEach(Taxonomy.groups) { group in
                Section {
                    ForEach(group.topics) { topic in
                        Button {
                            toggle(topic.id)
                        } label: {
                            HStack(alignment: .center, spacing: 12) {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(topic.name)
                                    Text(topic.covers)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                        .lineLimit(2)
                                }
                                Spacer()
                                checkmark(draft.contains(topic.id))
                            }
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                    }
                } header: {
                    HStack {
                        Text(group.name)
                        Spacer()
                        Button(allSelected(group) ? "Clear" : "Select all") { toggleGroup(group) }
                            .font(.caption.weight(.medium))
                            .textCase(nil)
                    }
                }
            }
        }
        .navigationTitle("Your topics")
        .safeAreaInset(edge: .bottom) { saveBar }
        .onAppear {
            if !loaded {
                draft = TopicPrefs.decode(followedRaw)
                loaded = true
            }
        }
        .alert("Papers updated", isPresented: Binding(
            get: { resultMessage != nil },
            set: { if !$0 { resultMessage = nil } }
        )) {
            Button("Done") { onFinish?() }
        } message: {
            Text(resultMessage ?? "")
        }
    }

    private var saveBar: some View {
        Button {
            Task { await save() }
        } label: {
            Group {
                if saving {
                    ProgressView().tint(.white)
                } else {
                    Text(draft.isEmpty ? "Save and refresh papers" : "Save and refresh papers · \(draft.count) topics")
                }
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 4)
        }
        .buttonStyle(.borderedProminent)
        .controlSize(.large)
        .disabled(saving)
        .padding()
        .background(.bar)
    }

    private func checkmark(_ on: Bool) -> some View {
        Image(systemName: on ? "checkmark.circle.fill" : "circle")
            .font(.title3)
            .foregroundStyle(on ? Color.accentColor : Color.secondary.opacity(0.5))
    }

    private func toggle(_ id: String) {
        if draft.contains(id) { draft.remove(id) } else { draft.insert(id) }
    }

    private func allSelected(_ group: TopicGroup) -> Bool {
        group.topics.allSatisfy { draft.contains($0.id) }
    }

    private func toggleGroup(_ group: TopicGroup) {
        let ids = group.topics.map(\.id)
        if allSelected(group) { draft.subtract(ids) } else { draft.formUnion(ids) }
    }

    /// Apply the topics to every day (filtering happens instantly, on the phone) and fetch
    /// the newest papers so today's picks are up to date.
    private func save() async {
        saving = true
        followedRaw = TopicPrefs.encode(draft)
        await store.refresh()
        saving = false
        let today = store.latest?.papers.filter { TopicPrefs.matches($0, draft) }.count ?? 0
        if draft.isEmpty {
            resultMessage = "You'll see the editor's picks across all topics, today and in every past report."
        } else if today == 0 {
            resultMessage = "Your topics are saved for today and every past report. There's nothing new in them today; you'll see the other highlights instead."
        } else {
            resultMessage = "Your topics are saved for today and every past report. \(today) paper\(today == 1 ? "" : "s") in your topics today."
        }
    }
}
