import Foundation
import Observation

@MainActor
@Observable
final class DigestStore {
    var index: DigestIndex?
    var latest: Digest?
    var isLoading = false
    var errorMessage: String?
    private var days: [String: Digest] = [:]

    init() {
        index = Self.readCache("index", as: DigestIndex.self)
        latest = Self.readCache("latest", as: Digest.self)
    }

    var feedBase: String {
        let raw = UserDefaults.standard.string(forKey: Config.feedURLKey) ?? Config.defaultFeedURL
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.hasSuffix("/") ? trimmed : trimmed + "/"
    }

    var isConfigured: Bool { !feedBase.contains("YOUR-GITHUB-USERNAME") }

    /// Download the newest index and digest. Keeps cached data if offline.
    func refresh() async {
        guard isConfigured else {
            errorMessage = "Add your report address in Settings first."
            return
        }
        isLoading = true
        defer { isLoading = false }
        do {
            let idx: DigestIndex = try await fetch("data/index.json")
            let newest: Digest = try await fetch("data/latest.json")
            index = idx
            latest = newest
            days[newest.date] = newest
            errorMessage = nil
        } catch {
            errorMessage = "Couldn't update: \(error.localizedDescription)"
        }
    }

    /// One day's digest, from memory, disk cache, or the network.
    func digest(for date: String) async throws -> Digest {
        if let d = days[date] { return d }
        if let d = Self.readCache(date, as: Digest.self) {
            days[date] = d
            return d
        }
        let d: Digest = try await fetch("data/\(date).json", cacheAs: date)
        days[date] = d
        return d
    }

    // MARK: - Networking & cache

    private func fetch<T: Decodable>(_ path: String, cacheAs name: String? = nil) async throws -> T {
        guard let url = URL(string: feedBase + path) else { throw URLError(.badURL) }
        var request = URLRequest(url: url)
        request.cachePolicy = .reloadIgnoringLocalCacheData
        request.timeoutInterval = 20
        let (data, response) = try await URLSession.shared.data(for: request)
        if let http = response as? HTTPURLResponse, http.statusCode != 200 {
            throw URLError(.badServerResponse, userInfo: [
                NSLocalizedDescriptionKey: "The server answered \(http.statusCode) for \(path). "
                    + "Check the address in Settings, or wait for the first daily run."])
        }
        let value = try Self.decoder.decode(T.self, from: data)
        let cacheName = name ?? (path.hasSuffix("index.json") ? "index" : "latest")
        Self.writeCache(cacheName, data: data)
        return value
    }

    private static let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }()

    private static var cacheDir: URL {
        let dir = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("digests", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    private static func writeCache(_ name: String, data: Data) {
        try? data.write(to: cacheDir.appendingPathComponent("\(name).json"), options: .atomic)
    }

    private static func readCache<T: Decodable>(_ name: String, as type: T.Type) -> T? {
        guard let data = try? Data(contentsOf: cacheDir.appendingPathComponent("\(name).json")) else { return nil }
        return try? decoder.decode(T.self, from: data)
    }
}
