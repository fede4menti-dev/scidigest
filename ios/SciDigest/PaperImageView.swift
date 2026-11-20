import SwiftUI

/// Large image with caption and credit, for the paper detail screen.
struct PaperImageView: View {
    let image: PaperImage

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            if let url = URL(string: image.url) {
                AsyncImage(url: url) { phase in
                    switch phase {
                    case .success(let img):
                        img.resizable().scaledToFit()
                    case .failure:
                        EmptyView()
                    default:
                        Rectangle().fill(.quaternary).frame(height: 200)
                            .overlay(ProgressView())
                    }
                }
                .frame(maxWidth: .infinity)
                .clipShape(RoundedRectangle(cornerRadius: 10))
            }
            if image.isIllustration {
                Text("Illustration, not from the paper")
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(.secondary)
            }
            if !image.caption.isEmpty {
                Text(image.caption)
                    .font(.footnote)
            }
            HStack(spacing: 4) {
                Text(image.credit)
                if !image.license.isEmpty {
                    Text("·")
                    if let s = image.licenseUrl, let licenseURL = URL(string: s) {
                        Link(image.license, destination: licenseURL)
                    } else {
                        Text(image.license)
                    }
                }
            }
            .font(.caption2)
            .foregroundStyle(.secondary)
        }
    }
}

/// Small square thumbnail for list rows.
struct PaperThumbnail: View {
    let image: PaperImage

    var body: some View {
        AsyncImage(url: URL(string: image.url)) { phase in
            if case .success(let img) = phase {
                img.resizable().scaledToFill()
            } else {
                Rectangle().fill(.quaternary)
            }
        }
        .frame(width: 64, height: 64)
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .accessibilityHidden(true)
    }
}
