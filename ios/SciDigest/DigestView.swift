import SwiftUI

/// A list of one digest's papers (daily, weekly or monthly).
/// Navigation destinations for Paper and ReviewEntry are declared by the NavigationStack root
/// (TodayView / ArchiveView), not here, so they are never registered twice.
struct DigestView: View {
    let digest: Digest
    var reviews: [ReviewEntry] = []

    var body: some View {
        List {
            Section {
                VStack(alignment: .leading, spacing: 6) {
                    if digest.isReview {
                        Text(digest.displayTitle)
                            .font(.title3.bold())
                    }
                    Label(digest.dateLine, systemImage: "calendar")
                        .font(.headline)
                    Text(digest.countLine)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    if let intro = digest.intro, !intro.isEmpty {
                        Text(intro)
                            .font(.callout)
                            .padding(.top, 4)
                    }
                    if !digest.aiSummaries && !digest.isReview {
                        Text("Summaries today are the original abstracts, not plain-language rewrites.")
                            .font(.footnote)
                            .foregroundStyle(.orange)
                    }
                }
                .padding(.vertical, 4)
            }

            if !reviews.isEmpty {
                Section("Reviews") {
                    ForEach(reviews) { review in
                        NavigationLink(value: review) {
                            ReviewRow(review: review)
                        }
                    }
                }
            }

            Section(digest.isReview ? "Top papers" : "Today's picks") {
                ForEach(digest.papers) { paper in
                    NavigationLink(value: paper) {
                        PaperRow(paper: paper, inReview: digest.isReview)
                    }
                }
            }
        }
        .listStyle(.insetGrouped)
    }
}

struct PaperRow: View {
    let paper: Paper
    var inReview = false

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            details
            if let image = paper.image {
                PaperThumbnail(image: image)
            }
        }
    }

    private var details: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                Chip(text: paper.field, color: Theme.color(for: paper.field))
                if paper.isFullText {
                    Chip(text: "Full text", color: .green, systemImage: "doc.text")
                }
                if !inReview && !paper.featuredDates.isEmpty {
                    Chip(text: "Featured before", color: .orange, systemImage: "arrow.clockwise")
                }
            }
            Text(paper.headline)
                .font(.headline)
                .fixedSize(horizontal: false, vertical: true)
            HStack {
                Text("\(paper.journal) · \(paper.publishedLabel)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Spacer()
                SignificanceMeter(score: paper.significance)
            }
        }
        .padding(.vertical, 4)
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
