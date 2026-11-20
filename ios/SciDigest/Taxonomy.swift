import SwiftUI

// Mirrors scidigest/taxonomy.py (tests/test_ios_contract.py checks the ids match).

struct Topic: Identifiable, Hashable {
    let id: String
    let name: String
    let covers: String
    let group: String
}

struct TopicGroup: Identifiable {
    let id: String
    let name: String
    let topics: [Topic]

    init(id: String, name: String, _ items: [(String, String, String)]) {
        self.id = id
        self.name = name
        self.topics = items.map { Topic(id: $0.0, name: $0.1, covers: $0.2, group: id) }
    }
}

enum Taxonomy {
    static let groups: [TopicGroup] = [
        TopicGroup(id: "physical", name: "Physical Sciences, Math & Computing", [
            ("physics", "Physics", "classical mechanics, quantum science, optics and photonics, condensed matter, mathematical physics, space physics"),
            ("chemistry", "Chemistry", "organic, inorganic, physical and analytical chemistry, chemical biology"),
            ("math_stats", "Mathematics & Statistics", "algebra, geometry, topology, differential equations, probability, numerical analysis, optimization, statistics theory"),
            ("computing", "Computer Science & IT", "artificial intelligence and machine learning, cybersecurity, data science, information theory, computational systems"),
            ("astronomy", "Astronomy & Planetary Science", "astrophysics, observational astronomy, planetary geology, cosmology"),
            ("materials", "Materials & Nanoscience", "nanomaterials, polymers, metallurgy, semiconductors, energy materials"),
        ]),
        TopicGroup(id: "engineering", name: "Engineering & Technology", [
            ("core_engineering", "Core Engineering", "mechanical, electrical, civil, chemical and aerospace engineering"),
            ("applied_tech", "Applied & Emerging Tech", "biomedical engineering, robotics, automation and control systems, energy science, biotechnology"),
        ]),
        TopicGroup(id: "life", name: "Biological & Life Sciences", [
            ("cell_molecular", "Cellular & Molecular", "cell biology, molecular biology, genetics, genomics, biochemistry, structural biology"),
            ("organismal", "Organismal & Systems", "microbiology, immunology, neuroscience, physiology, developmental biology, evolutionary biology"),
            ("ecology", "Ecology & Biodiversity", "ecology, conservation biology, zoology, plant sciences, entomology, computational biology and bioinformatics"),
        ]),
        TopicGroup(id: "health", name: "Health & Medical Sciences", [
            ("clinical", "Clinical & Disease Research", "oncology, cardiology, neurology, infectious diseases, clinical immunology"),
            ("therapeutics", "Therapeutics & Care", "pharmacology, drug discovery, nursing, dentistry, medical informatics, public and occupational health"),
            ("behavioral", "Behavioral & Mental Health", "clinical, cognitive, experimental and social psychology, behavioral sciences"),
        ]),
        TopicGroup(id: "earth", name: "Earth & Environmental Sciences", [
            ("earth_water", "Earth & Water", "geology (solid Earth), hydrology, ocean sciences, limnology, natural hazards"),
            ("climate", "Climate & Environment", "climate science, atmospheric science, environmental science, biogeochemistry, sustainability"),
        ]),
        TopicGroup(id: "society", name: "Society, Policy & Interdisciplinary Studies", [
            ("social_economic", "Social & Economic Sciences", "economics, finance, sociology, political science, public policy, education, geography"),
            ("resources", "Resource & Applied Fields", "agriculture, forestry, water resources, food science, veterinary science, science communication and ethics"),
        ]),
    ]

    static let all: [Topic] = groups.flatMap { $0.topics }
    static let order: [String: Int] = Dictionary(uniqueKeysWithValues: all.enumerated().map { ($1.id, $0) })

    static func topic(_ id: String?) -> Topic? {
        guard let id else { return nil }
        return all.first { $0.id == id }
    }
}

/// The topics a reader follows, stored as "id,id,id" in UserDefaults. Empty means all topics.
enum TopicPrefs {
    static let key = "followedTopics"
    static let onboardedKey = "didChooseTopics"

    static func decode(_ raw: String) -> Set<String> {
        Set(raw.split(separator: ",").map(String.init).filter { Taxonomy.topic($0) != nil })
    }

    static func encode(_ topics: Set<String>) -> String {
        topics.sorted().joined(separator: ",")
    }

    /// With no topics chosen everything matches; otherwise only papers tagged with a followed topic.
    static func matches(_ paper: Paper, _ followed: Set<String>) -> Bool {
        guard !followed.isEmpty else { return true }
        guard let c = paper.category else { return false }
        return followed.contains(c)
    }

    static func summary(_ followed: Set<String>) -> String {
        if followed.isEmpty { return "All topics" }
        let names = Taxonomy.all.filter { followed.contains($0.id) }.map(\.name)
        if names.count <= 2 { return names.joined(separator: ", ") }
        return "\(names[0]), \(names[1]) +\(names.count - 2)"
    }
}
