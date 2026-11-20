import SwiftUI

/// Medium-sized card: picture, topic, title, a short intro and the key facts.
/// Tapping it (via the surrounding NavigationLink) opens the full write-up.
struct PaperCard: View {
    let paper: Paper
    var compact = false
    var inReview = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            CardImage(paper: paper)
                .frame(height: compact ? 130 : 180)
                .frame(maxWidth: .infinity)
                .clipped()

            VStack(alignment: .leading, spacing: 6) {
                HStack(spacing: 6) {
                    Text(paper.topicLabel.uppercased())
                        .font(.caption2.weight(.semibold))
                        .tracking(0.6)
                        .foregroundStyle(Theme.color(for: paper))
                        .lineLimit(1)
                    if paper.isPreprint { Badge(text: "Preprint", color: .orange) }
                    if !compact && paper.isFullText { Badge(text: "Full text", color: .green) }
                    if !compact && !inReview && !paper.featuredDates.isEmpty { Badge(text: "Again", color: .blue) }
                }

                Text(paper.headline)
                    .font(compact ? .subheadline.weight(.semibold) : .headline)
                    .foregroundStyle(.primary)
                    .lineLimit(3)
                    .multilineTextAlignment(.leading)
                    .fixedSize(horizontal: false, vertical: true)

                if !compact {
                    Text(paper.intro)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .lineLimit(3)
                        .multilineTextAlignment(.leading)
                }

                Spacer(minLength: 0)

                HStack(spacing: 8) {
                    Text(paper.shortDate.isEmpty ? paper.journal : "\(paper.journal) · \(paper.shortDate)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                    Spacer(minLength: 4)
                    SignificanceMeter(score: paper.significance)
                }
                .padding(.top, 4)
            }
            .padding(14)
        }
        .frame(width: compact ? 260 : nil, height: compact ? 290 : nil)
        .background(Color(.secondarySystemGroupedBackground))
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .shadow(color: .black.opacity(0.06), radius: 10, y: 3)
        .accessibilityElement(children: .combine)
    }
}

private struct Badge: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text)
            .font(.caption2.weight(.semibold))
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .foregroundStyle(color)
            .background(color.opacity(0.13), in: RoundedRectangle(cornerRadius: 5, style: .continuous))
    }
}

/// The paper's image, or a tinted placeholder with a symbol for its field.
struct CardImage: View {
    let paper: Paper

    var body: some View {
        let tint = Theme.color(for: paper)
        ZStack {
            LinearGradient(colors: [tint.opacity(0.30), tint.opacity(0.10)],
                           startPoint: .topLeading, endPoint: .bottomTrailing)
            Image(systemName: Theme.symbol(for: paper))
                .font(.system(size: 34, weight: .light))
                .foregroundStyle(tint.opacity(0.75))
            if let s = paper.image?.url, let url = URL(string: s) {
                AsyncImage(url: url, transaction: Transaction(animation: .easeOut(duration: 0.2))) { phase in
                    if case .success(let img) = phase {
                        img.resizable().scaledToFill()
                    }
                }
            }
        }
        .accessibilityHidden(true)
    }
}
