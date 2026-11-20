import Foundation

enum Config {
    /// Your GitHub Pages address. Replace YOUR-GITHUB-USERNAME before building,
    /// or paste the address into the app's Settings tab.
    static let defaultFeedURL = "https://fede4menti-dev.github.io/scidigest/"

    static let feedURLKey = "feedURL"

    /// Idea checker server (Cloudflare Worker), e.g. "https://scidigest-idea-checker.yourname.workers.dev".
    /// Leave empty to use the built-in search-only mode. Can also be set in the app's Settings tab.
    static let defaultIdeaCheckerURL = ""
    /// Must match the IDEA_CHECKER_APP_TOKEN GitHub secret, if you set one.
    static let defaultIdeaCheckerToken = ""

    static let ideaCheckerURLKey = "ideaCheckerURL"
    static let ideaCheckerTokenKey = "ideaCheckerToken"
}
