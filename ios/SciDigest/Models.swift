import Foundation

// Mirrors the JSON written by scidigest/publish.py (format 1).
// Field names are snake_case in JSON and decoded with .convertFromSnakeCase.
// Fields added after the first release are optional so older files still decode.

struct DigestIndex: Codable {
    let format: Int
    let updated: String
    let days: [DayEntry]
    let weekly: [ReviewEntry]?
    let monthly: [ReviewEntry]?
}

struct DayEntry: Codable, Identifiable, Hashable {
    let date: String
    let count: Int
    let fields: [String]
    let topHeadlines: [String]

    var id: String { date }
    var displayDate: String { DayFormat.long(date) }
}

/// A weekly or monthly review in the index.
struct ReviewEntry: Codable, Identifiable, Hashable {
    let id: String
    let kind: String
    let title: String
    let periodStart: String
    let periodEnd: String
    let count: Int
    let topHeadlines: [String]

    var periodLabel: String { DayFormat.period(periodStart, periodEnd) }
    var badge: String { kind == "monthly" ? "Monthly review" : "Weekly review" }
}

struct Digest: Codable, Identifiable, Hashable {
    let format: Int
    let kind: String?
    let id: String?
    let title: String?
    let date: String
    let periodStart: String?
    let periodEnd: String?
    let generatedAt: String
    let scanned: Int
    let journals: [String]
    let aiSummaries: Bool
    let intro: String?
    let papers: [Paper]

    var isReview: Bool { (kind ?? "daily") != "daily" }
    var displayTitle: String { title ?? "Daily Science Digest" }
    var dateLine: String {
        if isReview, let s = periodStart, let e = periodEnd { return DayFormat.period(s, e) }
        return DayFormat.long(date)
    }
    var countLine: String {
        if isReview {
            return "The \(papers.count) most important papers of the \(kind == "monthly" ? "month" : "week"), "
                + "from \(scanned) featured in the daily digests"
        }
        return "\(papers.count) papers chosen from \(scanned) recent research articles in \(journals.count) journals"
    }
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
    let featuredOn: [String]?

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
    var publishedLabel: String {
        guard let p = published else { return "Publication date not listed" }
        return "Published " + DayFormat.short(String(p.prefix(10)))
    }
    /// Other days this paper appeared in the daily digest.
    var featuredDates: [String] { featuredOn ?? [] }
    var featuredLabel: String { featuredDates.map { DayFormat.short($0) }.joined(separator: ", ") }
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
    /// "2026-11-18" -> a Date at local midnight on that day.
    static func date(_ isoDay: String) -> Date? {
        let parts = isoDay.prefix(10).split(separator: "-").compactMap { Int($0) }
        guard parts.count == 3 else { return nil }
        return Calendar.current.date(from: DateComponents(year: parts[0], month: parts[1], day: parts[2]))
    }

    /// "Wednesday, November 18, 2026"
    static func long(_ isoDay: String) -> String {
        date(isoDay)?.formatted(date: .complete, time: .omitted) ?? isoDay
    }

    /// "Nov 18, 2026"
    static func short(_ isoDay: String) -> String {
        date(isoDay)?.formatted(date: .abbreviated, time: .omitted) ?? isoDay
    }

    /// "Nov 16, 2026 to Nov 22, 2026"
    static func period(_ start: String, _ end: String) -> String {
        "\(short(start)) to \(short(end))"
    }
}
