import SwiftUI

enum Theme {
    private static let palette: [Color] = [.blue, .teal, .indigo, .purple, .pink, .orange, .green, .mint, .cyan, .brown]

    /// Stable colour per field name (String.hashValue changes every launch, so sum scalars instead).
    static func color(for field: String) -> Color {
        let sum = field.lowercased().unicodeScalars.reduce(0) { $0 + Int($1.value) }
        return palette[sum % palette.count]
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
                    .frame(width: 5, height: 10)
            }
        }
        .accessibilityElement()
        .accessibilityLabel("Significance \(score) out of 10")
    }
}
