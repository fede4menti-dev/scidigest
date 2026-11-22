import SwiftUI

enum Theme {
    /// App tint: a calm teal.
    static let accent = Color(red: 0.06, green: 0.46, blue: 0.43)

    private static let groupColors: [String: Color] = [
        "physical": .indigo, "engineering": .orange, "life": .green,
        "health": .pink, "earth": .teal, "society": .purple,
    ]
    private static let groupSymbols: [String: String] = [
        "physical": "atom", "engineering": "gearshape.2", "life": "leaf",
        "health": "cross.case", "earth": "globe.europe.africa", "society": "person.3",
    ]
    private static let palette: [Color] = [.blue, .teal, .indigo, .purple, .pink, .orange, .green, .mint, .cyan, .brown]

    /// Colour for a paper: by its topic group, or a stable colour from its field name.
    static func color(for paper: Paper) -> Color {
        if let g = Taxonomy.topic(paper.category)?.group, let c = groupColors[g] { return c }
        return color(for: paper.field)
    }

    static func color(for field: String) -> Color {
        // String.hashValue changes every launch, so sum scalars instead.
        let sum = field.lowercased().unicodeScalars.reduce(0) { $0 + Int($1.value) }
        return palette[sum % palette.count]
    }

    static func symbol(for paper: Paper) -> String {
        if let g = Taxonomy.topic(paper.category)?.group, let s = groupSymbols[g] { return s }
        return "doc.text.image"
    }
}

struct Chip: View {
    let text: String
    var color: Color = .accentColor
    var systemImage: String? = nil

    var body: some View {
        HStack(spacing: 4) {
            if let systemImage { Image(systemName: systemImage) }
            Text(text)
        }
        .font(.caption.weight(.medium))
        .padding(.horizontal, 8)
        .padding(.vertical, 3)
        .foregroundStyle(color)
        .background(color.opacity(0.14), in: Capsule())
    }
}

struct SignificanceMeter: View {
    let score: Int

    var body: some View {
        HStack(spacing: 2) {
            ForEach(1...10, id: \.self) { i in
                Capsule()
                    .fill(i <= score ? Color.accentColor : Color.secondary.opacity(0.25))
                    .frame(width: 4, height: 9)
            }
        }
        .accessibilityElement()
        .accessibilityLabel("AI-estimated significance \(score) out of 10")
    }
}
