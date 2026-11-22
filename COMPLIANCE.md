# Compliance checklist

How SciDigest (website, iPhone app, Cloudflare server) handles each common app-compliance requirement.
**This is a practical checklist, not legal advice.** For a public launch, especially on the App Store, have the
privacy policy and terms reviewed by someone qualified for your country.

## Things only you can do

1. **Add your business details.** Repository → Settings → Secrets and variables → Actions → **Variables**:
   - `SCIDIGEST_OPERATOR`: who runs SciDigest, e.g. your full name or your company name.
   - `SCIDIGEST_CONTACT_EMAIL`: an address for privacy, deletion and copyright requests.
   Then run **Daily digest** once (no "force"; it's free) so the legal pages update.
   Until set, the pages say "the SciDigest maintainer" and link to GitHub issues for contact.
2. **If you change what data is collected,** update `scidigest/templates/legal/privacy.html.j2` and bump
   `LEGAL_VERSION` / `LEGAL_UPDATED` in `scidigest/report.py`. New sign-ups record the version they accepted.
3. **App Store:** in App Store Connect → App Privacy, the website-only account feature isn't in the app yet, so the
   app collects no data ("Data Not Collected"). If you add accounts to the app, declare *Email address* and
   *User content* (linked to the user, not used for tracking), and keep in-app account deletion.

## Checklist

| # | Requirement | Status | Where |
|---|---|---|---|
| 1 | Privacy policy | ✅ | `privacy.html`: what's collected, why, where, processors, retention, rights, children, security, contact |
| 2 | Terms of service | ✅ | `terms.html`: AI content, **not medical advice**, accounts 16+, acceptable use, copyright, liability |
| 3 | Refund policy | ✅ N/A | Free, no purchases: stated in Terms §2 |
| 4 | Cookie policy | ✅ | `cookies.html`: no cookies; every local-storage key, the offline cache and image requests listed |
| 5 | Cookie consent banner | ✅ | No cookies or tracking, only strictly necessary storage, so consent isn't required; a first-visit notice says so with a link |
| 6 | Form consents | ✅ | Sign-up: two **unticked, required** boxes (Terms + Privacy, 16+); the server rejects sign-ups without them and records version + time. Idea Check explains where questions are sent |
| 7 | No unnecessary data | ✅ | Account = email + hashes + synced settings only. IPs only in memory for 1 h. Idea-check cache not linked to people |
| 8 | Third-party SDK audit | ✅ | Website: no third-party scripts, fonts, trackers or analytics. iPhone app: no SDKs. Server: Anthropic SDK only. All outside services listed in the privacy policy |
| 9 | No dark patterns | ✅ | No pre-ticked boxes; Cancel always visible; delete account / export / reset are one place in Settings; no nagging |
| 10 | No hidden fees | ✅ | Free; stated in footer and Terms |
| 11 | No fake reviews | ✅ | No reviews or testimonials anywhere |
| 12 | No unsupported claims | ✅ | Copy says picks and summaries are by AI; significance labelled "AI-estimated"; AI and not-medical-advice notes on every page; Idea Check says a search can miss work |
| 13 | Alt text | ✅ | Photos use their caption/headline as alt text; decorative icons and placeholders are hidden from screen readers; the significance meter has a text label |
| 14 | Colour contrast | ✅ | axe-core scan (WCAG 2 AA + best practices): **0 violations** on all 11 pages and the settings sheet, light and dark |
| 15 | Keyboard navigation | ✅ | Skip-to-content link, visible 3px focus ring, settings and dialogs open with Enter and close with Esc (focus kept inside), cards open with Enter and close with Esc |
| 16 | Business details | ⚠️ you | Set `SCIDIGEST_OPERATOR` and `SCIDIGEST_CONTACT_EMAIL` (above) |
| 17 | Age consent for kids' data | ✅ | Accounts require confirming 16+; without an account no personal data is collected; children's section in the privacy policy |
| 18 | Unsubscribe link in emails | ✅ N/A | SciDigest sends no emails; stated in the privacy policy |
| 19 | Licensed fonts and images | ✅ | System fonts only; images only CC BY / BY-SA / CC0 / public domain with credit and licence on each; own icons; `credits.html` lists sources. Fallback text quotes at most two sentences of an abstract |
| 20 | Data deletion requests | ✅ | Settings → Delete account (immediate), Clear history, Reset device; export as JSON; contact route with a 30-day response commitment |
