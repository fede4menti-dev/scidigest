import Foundation

/// Talks to the idea checker worker. Without one configured, falls back to a plain
/// Europe PMC search from the phone (related papers only, no AI report).
enum IdeaChecker {
    enum Outcome {
        case report(IdeaReport)
        case searchOnly([RelatedPaper])
    }

    struct Failure: LocalizedError {
        let message: String
        var errorDescription: String? { message }
    }

    static var serverURL: String {
        (UserDefaults.standard.string(forKey: Config.ideaCheckerURLKey) ?? Config.defaultIdeaCheckerURL)
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }

    static func check(_ question: String) async throws -> Outcome {
        if serverURL.isEmpty {
            return .searchOnly(try await searchEuropePMC(question))
        }
        return .report(try await askServer(question))
    }

    private static let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }()

    private static func askServer(_ question: String) async throws -> IdeaReport {
        let base = serverURL.hasSuffix("/") ? String(serverURL.dropLast()) : serverURL
        guard let url = URL(string: base + "/check") else { throw Failure(message: "The idea checker address in Settings isn't valid.") }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 120   // searching + writing the report takes 20-60 seconds
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let token = UserDefaults.standard.string(forKey: Config.ideaCheckerTokenKey) ?? Config.defaultIdeaCheckerToken
        if !token.isEmpty { request.setValue(token, forHTTPHeaderField: "X-App-Token") }
        request.httpBody = try JSONEncoder().encode(["question": question])

        let (data, response) = try await URLSession.shared.data(for: request)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard status == 200 else {
            let msg = (try? decoder.decode(IdeaServerError.self, from: data))?.error
            throw Failure(message: msg ?? "The idea checker answered with an error (\(status)).")
        }
        return try decoder.decode(IdeaReport.self, from: data)
    }

    // MARK: - Fallback: Europe PMC search, straight from the phone

    private struct EPMCResponse: Decodable {
        struct List: Decodable { let result: [Item] }
        struct Item: Decodable {
            let id: String?
            let source: String?
            let title: String?
            let authorString: String?
            let pubYear: String?
            let journalTitle: String?
            let doi: String?
            let citedByCount: Int?
        }
        let resultList: List
    }

    static func searchEuropePMC(_ question: String) async throws -> [RelatedPaper] {
        var c = URLComponents(string: "https://www.ebi.ac.uk/europepmc/webservices/rest/search")!
        c.queryItems = [
            URLQueryItem(name: "query", value: question),
            URLQueryItem(name: "format", value: "json"),
            URLQueryItem(name: "resultType", value: "lite"),
            URLQueryItem(name: "pageSize", value: "15"),
        ]
        let (data, response) = try await URLSession.shared.data(from: c.url!)
        guard (response as? HTTPURLResponse)?.statusCode == 200 else {
            throw Failure(message: "Couldn't reach Europe PMC. Check your connection and try again.")
        }
        let items = try JSONDecoder().decode(EPMCResponse.self, from: data).resultList.result
        return items.compactMap { i in
            guard let title = i.title, !title.isEmpty else { return nil }
            let link = i.doi.map { "https://doi.org/\($0)" }
                ?? "https://europepmc.org/article/\(i.source ?? "MED")/\(i.id ?? "")"
            return RelatedPaper(title: title.hasSuffix(".") ? String(title.dropLast()) : title,
                                authors: i.authorString ?? "", year: i.pubYear.flatMap(Int.init),
                                venue: i.journalTitle ?? "", doi: i.doi, url: link, citedBy: i.citedByCount ?? 0,
                                source: "Europe PMC", relevance: "search result", howItRelates: "")
        }
    }
}
