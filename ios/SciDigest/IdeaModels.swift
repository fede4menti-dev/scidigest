import Foundation

// Mirrors the JSON returned by the idea checker worker (worker/src/checker.js).
// Decoded with .convertFromSnakeCase.

struct IdeaReport: Codable, Hashable {
    let question: String
    let field: String
    let verdict: String
    let noveltyScore: Int
    let overallScore: Int
    let summary: String
    let quality: QualityScores
    let ethics: String
    let gaps: [String]
    let suggestions: [String]
    let improvedQuestion: String
    let related: [RelatedPaper]
    let search: SearchInfo
    let generatedAt: String
}

struct QualityScores: Codable, Hashable {
    let clarity: Scored
    let specificity: Scored
    let feasibility: Scored
    let significance: Scored
    let testability: Scored

    var all: [QualityItem] {
        [QualityItem(name: "Clarity", value: clarity), QualityItem(name: "Specificity", value: specificity),
         QualityItem(name: "Feasibility", value: feasibility), QualityItem(name: "Significance", value: significance),
         QualityItem(name: "Testability", value: testability)]
    }
}

struct QualityItem: Identifiable {
    let name: String
    let value: Scored
    var id: String { name }
}

struct Scored: Codable, Hashable {
    let score: Int
    let comment: String
}

struct RelatedPaper: Codable, Hashable, Identifiable {
    let title: String
    let authors: String
    let year: Int?
    let venue: String
    let doi: String?
    let url: String
    let citedBy: Int
    let source: String
    let relevance: String
    let howItRelates: String

    var id: String { doi ?? url }
    var metaLine: String {
        [authors, year.map(String.init), venue].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: " · ")
    }
}

struct SearchInfo: Codable, Hashable {
    let queries: [String]
    let sources: [String]
    let papersConsidered: Int
    let failures: [String]
}

struct IdeaServerError: Codable {
    let error: String
}
