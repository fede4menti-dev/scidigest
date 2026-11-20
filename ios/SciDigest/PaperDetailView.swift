import SwiftUI
import UIKit

struct PaperDetailView: View {
    let paper: Paper
    @State private var copied = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                HStack(spacing: 6) {
                    Chip(text: paper.topicLabel, color: Theme.color(for: paper))
                    if paper.isPreprint {
                        Chip(text: "Preprint, not peer reviewed", color: .orange)
                    }
                    if paper.isFullText {
                        Chip(text: "From full text", color: .green, systemImage: "doc.text")
                    }
                }

                VStack(alignment: .leading, spacing: 6) {
                    Text(paper.headline)
                        .font(.title2.bold())
                    Text(paper.journal)
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(.secondary)
                    Text("Original title: \u{201C}\(paper.originalTitle)\u{201D}")
                        .font(.subheadline)
                        .italic()
                        .foregroundStyle(.secondary)
                    Label(paper.publishedLabel, systemImage: "calendar")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                    if !paper.featuredDates.isEmpty {
                        Label("In the daily digest on \(paper.featuredLabel)", systemImage: "arrow.clockwise")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                    if !paper.authorLine.isEmpty {
                        Text(paper.authorLine)
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                    HStack {
                        Text("Significance")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        SignificanceMeter(score: paper.significance)
                        Text("\(paper.significance)/10")
                            .font(.caption.monospacedDigit())
                            .foregroundStyle(.secondary)
                    }
                }

                if let image = paper.image {
                    PaperImageView(image: image)
                }

                VStack(alignment: .leading, spacing: 12) {
                    ForEach(paper.paragraphs, id: \.self) { para in
                        Text(para)
                    }
                }

                DetailSection(title: "Why it matters", systemImage: "lightbulb") {
                    Text(paper.whyItMatters)
                }

                if !paper.limitations.isEmpty {
                    DetailSection(title: "Caveats", systemImage: "exclamationmark.triangle") {
                        Text(paper.limitations)
                    }
                }

                if !paper.keyTerms.isEmpty {
                    DetailSection(title: "Key terms", systemImage: "character.book.closed") {
                        VStack(alignment: .leading, spacing: 8) {
                            ForEach(paper.keyTerms, id: \.term) { t in
                                Text("**\(t.term):** \(t.meaning)")
                            }
                        }
                    }
                }

                if !paper.reason.isEmpty {
                    DetailSection(title: "Why it was picked", systemImage: "star") {
                        Text(paper.reason)
                    }
                }

                sourceBox
            }
            .padding()
        }
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if let url = URL(string: paper.url) {
                ShareLink(item: url, subject: Text(paper.headline), message: Text(paper.headline))
            }
        }
    }

    private var sourceBox: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("Source", systemImage: "quote.opening")
                .font(.headline)
            Text(paper.citation)
                .font(.footnote)
                .textSelection(.enabled)

            Button {
                UIPasteboard.general.string = paper.citation
                copied = true
            } label: {
                Label(copied ? "Citation copied" : "Copy citation (APA)",
                      systemImage: copied ? "checkmark" : "doc.on.doc")
            }
            .buttonStyle(.bordered)

            if let url = URL(string: paper.url) {
                Link(destination: url) {
                    Label("Read the original paper", systemImage: "arrow.up.right.square")
                }
            }
            if let free = paper.freeCopy, let url = URL(string: free.url) {
                Link(destination: url) {
                    VStack(alignment: .leading, spacing: 2) {
                        Label("Free to read: \(free.version)", systemImage: "lock.open")
                        Text("via \(free.host)" + (free.license.map { ", \($0)" } ?? ""))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            Text(paper.basedOn.contains("not paraphrased")
                 ? "This text is the publisher's abstract. Check the original before citing it in your own work."
                 : "Summary paraphrased by AI from the paper's \(paper.basedOn). Check the original before citing it in your own work.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 12))
    }
}

struct DetailSection<Content: View>: View {
    let title: String
    let systemImage: String
    @ViewBuilder let content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Label(title, systemImage: systemImage)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(.secondary)
                .textCase(.uppercase)
            content
        }
    }
}
