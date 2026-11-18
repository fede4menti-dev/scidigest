import SwiftUI

/// A list of one day's papers. Must be shown inside a NavigationStack.
struct DigestView: View {
    let digest: Digest

    var body: some View {
        List {
            Section {
                VStack(alignment: .leading, spacing: 4) {
                    Text(digest.displayDate)
                        .font(.headline)
                    Text("\(digest.papers.count) papers chosen from \(digest.scanned) new research articles in \(digest.journals.count) journals")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    if !digest.aiSummaries {
                        Text("Summaries today are the original abstracts, not plain-language rewrites.")
                            .font(.footnote)
                            .foregroundStyle(.orange)
                    }
                }
                .padding(.vertical, 4)
            }

            Section("Top picks") {
                ForEach(digest.papers) { paper in
                    NavigationLink(value: paper) {
                        PaperRow(paper: paper)
                    }
                }
            }
        }
        .listStyle(.insetGrouped)
        .navigationDestination(for: Paper.self) { PaperDetailView(paper: $0) }
    }
}

struct PaperRow: View {
    let paper: Paper

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                Chip(text: paper.field, color: Theme.color(for: paper.field))
                if paper.isFullText {
                    Chip(text: "Full text", color: .green, systemImage: "doc.text")
                }
            }
            Text(paper.headline)
                .font(.headline)
                .fixedSize(horizontal: false, vertical: true)
            HStack {
                Text(paper.journal)
                    .font(.caption)
                    .italic()
                    .foregroundStyle(.secondary)
                Spacer()
                SignificanceMeter(score: paper.significance)
            }
        }
        .padding(.vertical, 4)
    }
}
