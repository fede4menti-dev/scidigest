import Foundation

// Mirrors the JSON written by scidigest/publish.py (format 1).
// Field names are snake_case in JSON and decoded with .convertFromSnakeCase.

struct DigestIndex: Codable {
    let format: Int
    let updated: String
    let days: [DayEntry]
}

struct DayEntry: Codable, Identifiable, Hashable {
    let date: String
    let count: Int
    let fields: [String]
    let topHeadlines: [String]

    var id: String { date }
    var displayDate: String { DayFormat.display(date) }
}

struct Digest: Codable, Identifiable, Hashable {
    let format: Int
    let date: String
    let generatedAt: String
    let scanned: Int
    let journals: [String]
    let aiSummaries: Bool
    let papers: [Paper]

    var id: String { date }
    var displayDate: String { DayFormat.display(date) }
}

struct Paper: Codable, Identifiable, Hashable {
    let rank: Int
    let headline: String
    let originalTitle: String
    let journal: String
    let field: String
    let significance: Int
    let reason: String
    let summary: String
    let whyItMatters: String
    let limitations: String
    let keyTerms: [KeyTerm]
    let basedOn: String
    let authors: [String]
    let published: String?
    let doi: String?
    let url: String
    let citation: String
    let freeCopy: FreeCopy?

    var id: String { "\(rank)-\(url)" }
    var isFullText: Bool { basedOn == "full text" }
    var paragraphs: [String] {
        summary.split(separator: "\n").map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
    }
    var authorLine: String {
        switch authors.count {
        case 0: return ""
        case 1: return authors[0]
        case 2: return "\(authors[0]) & \(authors[1])"
        default: return "\(authors[0]) et al."
        }
    }
}

struct KeyTerm: Codable, Hashable {
    let term: String
    let meaning: String
}

struct FreeCopy: Codable, Hashable {
    let url: String
    let version: String
    let host: String
    let license: String?
}

enum DayFormat {
    /// "2026-11-18" -> "Wednesday, November 18, 2026" in the phone's own calendar and time zone.
    static func display(_ isoDay: String) -> String {
        let parts = isoDay.split(separator: "-").compactMap { Int($0) }
        guard parts.count == 3,
              let d = Calendar.current.date(from: DateComponents(year: parts[0], month: parts[1], day: parts[2]))
        else { return isoDay }
        return d.formatted(date: .complete, time: .omitted)
    }
}
