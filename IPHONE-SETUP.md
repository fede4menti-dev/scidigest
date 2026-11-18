# Putting SciDigest on your iPhone

How it fits together:

```
GitHub (free, runs every morning)              Your iPhone
┌──────────────────────────────────┐          ┌──────────────────────┐
│ Python app scans journals,       │  JSON    │ SciDigest app shows  │
│ Claude writes summaries,         │ ───────▶ │ today's picks, the   │
│ publishes to GitHub Pages        │          │ archive, citations   │
└──────────────────────────────────┘          └──────────────────────┘
```

Your Anthropic API key lives only in GitHub's encrypted secrets, never inside the phone app.

**You need:** a GitHub account (free), an Anthropic API key with some credit, a Mac with Xcode (free from the Mac App Store), your iPhone, and your Apple Developer account.

---

## Part A: Make the reports run every morning (GitHub)

**A1. Create a repository**
1. Go to github.com and sign in.
2. Click **+** (top right) → **New repository**.
3. Name it exactly `scidigest`. Choose **Public** (GitHub Pages is free for public repos). Click **Create repository**.

**A2. Upload the code**
The easiest way is **GitHub Desktop** (desktop.github.com), because it handles the hidden `.github` folder that the browser upload can miss:
1. Install GitHub Desktop and sign in.
2. **File → Clone repository** → pick `scidigest` → choose a location → **Clone**.
3. Copy everything from inside the unzipped `scidigest` folder into the cloned folder. On a Mac, press `Cmd + Shift + .` in Finder to show hidden files, so the `.github` folder gets copied too.
4. Back in GitHub Desktop, type a summary like "First version" → **Commit to main** → **Push origin**.

**A3. Add your secrets**
1. On github.com, open your `scidigest` repo → **Settings** → **Secrets and variables** → **Actions**.
2. **New repository secret**: Name `ANTHROPIC_API_KEY`, Secret = your key (`sk-ant-...`). Save.
3. **New repository secret**: Name `SCIDIGEST_EMAIL`, Secret = your email (used for the Unpaywall free-copy search). Save.

**A4. Run it the first time**
1. Go to the **Actions** tab. If asked, click **I understand my workflows, go ahead and enable them**.
2. Click **Daily digest** on the left → **Run workflow** → **Run workflow**.
3. Wait 3 to 8 minutes for a green tick. A red cross means something failed: click it, copy the log, and send it to Claude.

**A5. Turn on the website**
1. **Settings** → **Pages**.
2. Under **Build and deployment**: Source **Deploy from a branch**, Branch **main**, folder **/docs** → **Save**.
3. After a minute or two, open `https://YOUR-GITHUB-USERNAME.github.io/scidigest/` in a browser. You should see today's report listed. Keep this address, the app needs it.

From now on it runs by itself every day at 10:17 UTC (about 5am US Eastern, 10am UK in winter). To change the time, edit the `cron:` line in `.github/workflows/daily-digest.yml`.

---

## Part B: Build the iPhone app (Mac + Xcode)

**B1. Create the Xcode project**
1. Open Xcode → **Create New Project** (or File → New → Project).
2. Choose **iOS** → **App** → **Next**.
3. Product Name: `SciDigest`. Interface: **SwiftUI**. Language: **Swift**. Storage: **None**. Leave testing options unticked. **Next**, pick a folder, **Create**.

**B2. Swap in the SciDigest code**
1. In the left sidebar, find `ContentView.swift` and `SciDigestApp.swift` (inside the yellow `SciDigest` folder). Select both → right-click → **Delete** → **Move to Trash**.
2. In Finder, open `scidigest/ios/SciDigest/` and select all 11 `.swift` files.
3. Drag them onto the yellow `SciDigest` folder in Xcode's sidebar. In the dialog, tick **Copy items if needed** and make sure the **SciDigest** target is ticked → **Finish**.

**B3. Set your report address**
Open `Config.swift` and replace `YOUR-GITHUB-USERNAME` with your GitHub username. You can also paste the address into the app's Settings tab later.

**B4. Set the minimum iOS version**
Click the blue **SciDigest** project at the top of the sidebar → **SciDigest** target → **General** → **Minimum Deployments** → set iOS to **17.0** or higher.

**B5. Add the app icon**
1. In Xcode's sidebar, click **Assets** (the `Assets.xcassets` catalog) → **AppIcon**.
2. Drag `scidigest/ios/AppIcon/AppIcon-1024.png` onto the empty **1024×1024** slot (the "Any Appearance" one). Xcode makes all the smaller sizes from it.

**B6. Try it in the simulator first**
At the top of Xcode pick a simulator such as **iPhone 16**, then press the ▶ (Run) button. The app opens on a virtual iPhone.

**B7. Sign it with your developer account**
1. Xcode → **Settings** → **Accounts** → **+** → **Apple ID** → sign in with the Apple ID that has your Apple Developer membership.
2. Project → **Signing & Capabilities** → tick **Automatically manage signing** → **Team**: pick your **developer team** (your name or company, *not* "Personal Team").
3. **Bundle Identifier**: make it unique to you, like `com.yourname.scidigest`. You can't change it once it's on the App Store.

**B8. Put it on your iPhone directly (quickest test)**
1. Plug in your iPhone and tap **Trust** on the phone.
2. On the iPhone: **Settings → Privacy & Security → Developer Mode** → on, then restart when asked.
3. In Xcode, pick your iPhone at the top and press ▶.

With your paid account this install lasts a year. For anything nicer (no cable, auto-updates, sharing), use TestFlight below.

---

## Part C: TestFlight (install without a cable, share with friends)

**C1. Create the app in App Store Connect**
1. Go to appstoreconnect.apple.com → **Apps** → **+** → **New App**.
2. Platform **iOS**, Name **SciDigest** (if taken, try "SciDigest Daily" or similar), Language **English**, Bundle ID: pick the one from B7, SKU: anything like `scidigest001`. **Create**.

**C2. Upload a build from Xcode**
1. In Xcode, at the top, choose **Any iOS Device (arm64)** as the destination.
2. Menu **Product → Archive**. Wait for it to finish; the **Organizer** window opens.
3. Select the archive → **Distribute App** → **App Store Connect** → **Distribute** (accept the defaults).
4. Wait 10 to 30 minutes for Apple to process it. You'll get an email.
5. If asked about **encryption** (Export Compliance): choose **None of the algorithms mentioned above**. The app only uses standard HTTPS.

**C3. Install it on your phone**
1. In App Store Connect → your app → **TestFlight** tab.
2. Under **Internal Testing**, click **+** to make a group, and add yourself.
3. Install the **TestFlight** app from the App Store on your iPhone, open the invite email, and tap **Install**.

**C4. Share with others (optional)**
TestFlight → **External Testing** → **+** → add a group → add the build → **Enable public link**. Anyone with the link can install it (up to 10,000 people). The first external build gets a quick Apple review, usually within a day. Fill in **Test Information** (a one-line description and your email) when asked.

Each new version: bump **Build** number in the target's **General** tab (1, 2, 3...), then repeat C2.

---

## Part D: Publishing on the App Store (optional)

In App Store Connect → your app → **App Store** tab, fill in:

| Field | What to put |
|---|---|
| Screenshots | Take them in the iPhone 16 Pro Max simulator (`Cmd + S` saves one to your Desktop). At least 3. |
| Description | e.g. "The day's most significant new research from Nature, Science, Cell, NEJM and more, explained in plain language for science students, with citations and links to every source." |
| Keywords | science, research, news, nature, biology, physics, students, papers |
| Support URL | Your GitHub Pages address |
| Privacy Policy URL | `https://YOUR-GITHUB-USERNAME.github.io/scidigest/privacy.html` (published automatically) |
| App Privacy | Click **Get Started** → **No, we do not collect data from this app** |
| Category | Education (or News) |
| Age rating | Answer "None" to everything |

Then pick your build, and click **Add for Review** → **Submit**.

Things that help it pass review:
- **Make sure `Config.swift` has your real address** before you archive, so the reviewer sees reports immediately instead of the "Almost there" screen.
- **Mention AI in the description**, e.g. "Summaries are written by AI from published abstracts and open-access papers, with a link to every original." The app already says this inside.
- **Keep the GitHub workflow running**, since the reviewer will open the app on a random day.

---

## Using the app

- **Today:** today's picks. Pull down to refresh. Tap any paper for the full explanation, caveats, key terms, citation (with a copy button), and links to the original and any free full-text copy.
- **Archive:** every past day.
- **Settings:** report address and an optional daily reminder notification (set it for a time after the report runs).

## Troubleshooting

| Problem | Fix |
|---|---|
| App says "server answered 404" | GitHub Pages isn't on yet (A5), or the first run hasn't finished (A4), or the address in Settings is wrong. |
| Action fails with "No ANTHROPIC_API_KEY set" | The secret name in A3 must be exactly `ANTHROPIC_API_KEY`. |
| Action fails with a credit or billing error | Add credit at console.anthropic.com → Billing. |
| Archive or upload fails with a signing error | Check B7: the Team must be your developer team, not "Personal Team". |
| Xcode build errors | Copy the red error text and send it to Claude. |
| Scheduled runs stopped | GitHub pauses schedules on repos with no activity for 60 days; the daily commits normally prevent this. If it happens, open Actions and re-enable it. |
