import SwiftUI

/// One digest (daily, weekly or monthly) as cards, filtered by the reader's topics.
/// Navigation destinations for Paper and ReviewEntry are declared by the NavigationStack root
/// (TodayView / ArchiveView), not here, so they are never registered twice.
struct DigestView: View {
    let digest: Digest
    var reviews: [ReviewEntry] = []

    @AppStorage(TopicPrefs.key) private var followedRaw = ""
    @State private var showTopics = false

    private var followed: Set<String> { TopicPrefs.decode(followedRaw) }

    private func sorted(_ papers: [Paper]) -> [Paper] {
        papers.sorted { a, b in
            if a.isEditorsPick != b.isEditorsPick { return a.isEditorsPick }
            if a.isEditorsPick { return a.rank < b.rank }
            return a.significance > b.significance
        }
    }

    private var forYou: [Paper] { sorted(digest.papers.filter { TopicPrefs.matches($0, followed) }) }
    private var editors: [Paper] { digest.papers.filter(\.isEditorsPick) }
    private var otherEditors: [Paper] { editors.filter { !TopicPrefs.matches($0, followed) } }

    private struct TopicSection: Identifiable {
        let id: String
        let title: String
        let papers: [Paper]
    }

    private var moreByTopic: [TopicSection] {
        let others = digest.papers.filter { !$0.isEditorsPick }
        let grouped = Dictionary(grouping: others) { $0.category ?? "other" }
        return grouped.keys
            .sorted { (Taxonomy.order[$0] ?? 99) < (Taxonomy.order[$1] ?? 99) }
            .map { key in
                let papers = grouped[key]!.sorted { $0.significance > $1.significance }
                return TopicSection(id: key, title: papers.first?.topicLabel ?? "More", papers: papers)
            }
    }

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 22) {
                header
                topicsBar
                if !reviews.isEmpty { reviewsRow }

                if followed.isEmpty {
                    cardList(title: digest.isReview ? "Top papers" : "Editor's picks", papers: editors)
                    if !moreByTopic.isEmpty {
                        Text("More by topic").font(.title3.bold()).padding(.top, 4)
                        ForEach(moreByTopic) { section in
                            carousel(title: section.title, papers: section.papers)
                        }
                    }
                } else {
                    if forYou.isEmpty {
                        emptyForYou
                    } else {
                        cardList(title: "For you", papers: forYou)
                    }
                    if !otherEditors.isEmpty {
                        carousel(title: "Also worth reading", papers: otherEditors)
                    }
                }

                Text("Summaries are written by AI from each paper's abstract or open-access full text. Preprints have not been peer reviewed. Check the original before citing it.")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
                    .padding(.top, 8)
            }
            .padding(.horizontal)
            .padding(.bottom, 24)
        }
        .background(Color(.systemGroupedBackground))
        .sheet(isPresented: $showTopics) {
            NavigationStack {
                TopicsView { showTopics = false }
                    .toolbar {
                        ToolbarItem(placement: .cancellationAction) {
                            Button("Cancel") { showTopics = false }
                        }
                    }
            }
        }
    }

    // MARK: - Pieces

    private var header: some View {
        VStack(alignment: .leading, spacing: 4) {
            if digest.isReview {
                Text(digest.displayTitle).font(.title2.bold())
            }
            Text(digest.dateLine.uppercased())
                .font(.caption.weight(.semibold))
                .tracking(0.5)
                .foregroundStyle(.secondary)
            Text(digest.countLine)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            if let intro = digest.intro, !intro.isEmpty {
                Text(intro).font(.callout).padding(.top, 6)
            }
            if !digest.aiSummaries && !digest.isReview {
                Text("Today's summaries are the original abstracts, not plain-language rewrites.")
                    .font(.footnote)
                    .foregroundStyle(.orange)
                    .padding(.top, 4)
            }
        }
        .padding(.top, 8)
    }

    private var topicsBar: some View {
        Button { showTopics = true } label: {
            HStack(spacing: 10) {
                Image(systemName: "line.3.horizontal.decrease.circle")
                    .font(.title3)
                VStack(alignment: .leading, spacing: 1) {
                    Text(followed.isEmpty ? "Showing all topics" : "Your topics")
                        .font(.subheadline.weight(.semibold))
                    Text(TopicPrefs.summary(followed))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
                Spacer()
                Text(followed.isEmpty ? "Choose" : "Edit")
                    .font(.subheadline.weight(.medium))
            }
            .padding(12)
            .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
        }
        .buttonStyle(.plain)
        .foregroundStyle(.primary)
    }

    private var reviewsRow: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Reviews").font(.title3.bold())
            ForEach(reviews) { review in
                NavigationLink(value: review) {
                    ReviewRow(review: review)
                        .padding(12)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color(.secondarySystemGroupedBackground),
                                    in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                }
                .buttonStyle(.plain)
            }
        }
    }

    private var emptyForYou: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("For you").font(.title3.bold())
            Text("Nothing new in your topics in this report. Here are the other highlights instead, or add more topics.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
    }

    private func cardList(title: String, papers: [Paper]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title).font(.title3.bold())
            ForEach(papers) { paper in
                NavigationLink(value: paper) {
                    PaperCard(paper: paper, inReview: digest.isReview)
                }
                .buttonStyle(.plain)
            }
        }
    }

    private func carousel(title: String, papers: [Paper]) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title.uppercased())
                .font(.caption.weight(.semibold))
                .tracking(0.6)
                .foregroundStyle(.secondary)
            ScrollView(.horizontal, showsIndicators: false) {
                LazyHStack(spacing: 12) {
                    ForEach(papers) { paper in
                        NavigationLink(value: paper) {
                            PaperCard(paper: paper, compact: true, inReview: digest.isReview)
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(.vertical, 6)
                .padding(.horizontal, 2)
            }
        }
    }
}

struct ReviewRow: View {
    let review: ReviewEntry

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Chip(text: review.badge, color: review.kind == "monthly" ? .purple : .indigo,
                 systemImage: review.kind == "monthly" ? "calendar" : "calendar.badge.clock")
            Text(review.title)
                .font(.headline)
            Text(review.periodLabel)
                .font(.caption)
                .foregroundStyle(.secondary)
            ForEach(review.topHeadlines.prefix(2), id: \.self) { h in
                Text("• " + h)
                    .font(.subheadline)
                    .lineLimit(1)
            }
        }
        .padding(.vertical, 2)
    }
}

/// Loads a digest by name (a date or a review id) and shows it.
struct DigestLoaderView: View {
    @Environment(DigestStore.self) private var store
    let name: String
    let title: String
    @State private var digest: Digest?
    @State private var error: String?

    var body: some View {
        Group {
            if let digest {
                DigestView(digest: digest)
            } else if let error {
                ContentUnavailableView("Couldn't load this report", systemImage: "wifi.exclamationmark",
                                       description: Text(error))
            } else {
                ProgressView()
            }
        }
        .navigationTitle(title)
        .navigationBarTitleDisplayMode(.inline)
        .task {
            do { digest = try await store.digest(for: name) }
            catch { self.error = error.localizedDescription }
        }
    }
}
