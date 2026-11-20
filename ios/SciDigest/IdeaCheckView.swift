import SwiftUI

struct IdeaCheckView: View {
    @State private var question = ""
    @State private var isChecking = false
    @State private var outcome: IdeaChecker.Outcome?
    @State private var errorMessage: String?
    @FocusState private var editing: Bool

    private var canCheck: Bool {
        question.trimmingCharacters(in: .whitespacesAndNewlines).count >= 15 && !isChecking
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    inputCard
                    if isChecking { progressCard }
                    if let errorMessage {
                        Label(errorMessage, systemImage: "exclamationmark.triangle")
                            .foregroundStyle(.red)
                            .font(.callout)
                    }
                    switch outcome {
                    case .report(let report): ReportView(report: report) { question = $0 }
                    case .searchOnly(let papers): SearchOnlyView(papers: papers)
                    case nil: EmptyView()
                    }
                }
                .padding()
            }
            .scrollDismissesKeyboard(.interactively)
            .navigationTitle("Idea Check")
        }
    }

    private var inputCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Has your research question already been studied? Get the most important related papers and a review of the question itself.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            TextField("e.g. Does daily walking improve memory in adults over 65?", text: $question, axis: .vertical)
                .lineLimit(3...8)
                .focused($editing)
                .padding(12)
                .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 10))
            Button {
                Task { await run() }
            } label: {
                Label("Check my idea", systemImage: "magnifyingglass")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .disabled(!canCheck)
        }
    }

    private var progressCard: some View {
        HStack(spacing: 12) {
            ProgressView()
            Text("Searching the literature and writing your report. This takes about 30 to 60 seconds.")
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 10))
    }

    private func run() async {
        editing = false
        isChecking = true
        errorMessage = nil
        outcome = nil
        defer { isChecking = false }
        do {
            outcome = try await IdeaChecker.check(question.trimmingCharacters(in: .whitespacesAndNewlines))
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

// MARK: - Full AI report

private struct ReportView: View {
    let report: IdeaReport
    let useQuestion: (String) -> Void

    private var verdictColor: Color {
        switch report.verdict {
        case "already well researched": return .orange
        case "partly researched": return .blue
        default: return .green
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            VStack(alignment: .leading, spacing: 8) {
                Chip(text: report.verdict.capitalized, color: verdictColor, systemImage: "books.vertical")
                HStack(spacing: 16) {
                    ScoreBadge(title: "Novelty", score: report.noveltyScore)
                    ScoreBadge(title: "Question quality", score: report.overallScore)
                }
                Text(report.summary)
            }
            .padding()
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(verdictColor.opacity(0.08), in: RoundedRectangle(cornerRadius: 12))

            DetailSection(title: "Quality of your question", systemImage: "checklist") {
                VStack(alignment: .leading, spacing: 10) {
                    ForEach(report.quality.all) { item in
                        VStack(alignment: .leading, spacing: 3) {
                            HStack {
                                Text(item.name).font(.subheadline.weight(.semibold))
                                Spacer()
                                SignificanceMeter(score: item.value.score)
                                Text("\(item.value.score)/10").font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                            }
                            Text(item.value.comment).font(.footnote).foregroundStyle(.secondary)
                        }
                    }
                    Text("Ethics: \(report.ethics)").font(.footnote)
                }
            }

            if !report.related.isEmpty {
                DetailSection(title: "Most important related research", systemImage: "doc.text.magnifyingglass") {
                    VStack(alignment: .leading, spacing: 14) {
                        ForEach(report.related) { RelatedRow(paper: $0) }
                    }
                }
            }

            if !report.gaps.isEmpty {
                DetailSection(title: "What's still open", systemImage: "questionmark.circle") {
                    Bullets(items: report.gaps)
                }
            }

            if !report.suggestions.isEmpty {
                DetailSection(title: "How to make it stronger", systemImage: "wand.and.stars") {
                    Bullets(items: report.suggestions)
                }
            }

            DetailSection(title: "Suggested version", systemImage: "pencil.and.outline") {
                VStack(alignment: .leading, spacing: 8) {
                    Text(report.improvedQuestion).italic()
                    Button("Check this version") { useQuestion(report.improvedQuestion) }
                        .font(.footnote)
                }
            }

            Text("Searched \(report.search.sources.joined(separator: " and ")) with: "
                 + report.search.queries.map { "\u{201C}\($0)\u{201D}" }.joined(separator: ", ")
                 + ". \(report.search.papersConsidered) papers reviewed. A search can miss work, so treat "
                 + "\u{201C}little prior research\u{201D} as a starting point, not proof.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }
}

private struct ScoreBadge: View {
    let title: String
    let score: Int

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title).font(.caption).foregroundStyle(.secondary)
            Text("\(score)/10").font(.title3.bold().monospacedDigit())
        }
    }
}

private struct Bullets: View {
    let items: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            ForEach(items, id: \.self) { Text("• " + $0) }
        }
    }
}

private struct RelatedRow: View {
    let paper: RelatedPaper

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            if paper.relevance != "search result" {
                Chip(text: paper.relevance.capitalized,
                     color: paper.relevance == "directly addresses it" ? .orange : .blue)
            }
            if let url = URL(string: paper.url) {
                Link(paper.title, destination: url).font(.subheadline.weight(.semibold))
            } else {
                Text(paper.title).font(.subheadline.weight(.semibold))
            }
            Text(paper.metaLine + (paper.citedBy > 0 ? " · cited \(paper.citedBy)×" : ""))
                .font(.caption)
                .foregroundStyle(.secondary)
            if !paper.howItRelates.isEmpty {
                Text(paper.howItRelates).font(.footnote)
            }
        }
    }
}

// MARK: - Search-only fallback

private struct SearchOnlyView: View {
    let papers: [RelatedPaper]

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Showing related papers from Europe PMC. For the full report (verdict, the most important papers and a review of your question), set up the idea checker and add its address in Settings.")
                .font(.footnote)
                .foregroundStyle(.secondary)
            if papers.isEmpty {
                Text("No papers found. Try different wording.")
            }
            ForEach(papers) { RelatedRow(paper: $0) }
        }
    }
}
