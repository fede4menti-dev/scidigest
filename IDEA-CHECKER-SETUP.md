# Setting up the Idea Checker

The Idea Check tab in the app takes a research question and returns:

- **A verdict:** already well researched / partly researched / little prior research found, with a novelty score.
- **The most important related papers** (up to 10), found in OpenAlex and Europe PMC and ranked by relevance and citations, each with one line on how it relates.
- **A quality review of the question:** clarity, specificity, feasibility, significance and testability (each 1 to 10 with a comment), plus ethics.
- **What's still open, how to make the question stronger, and an improved version** you can check again.

It runs on a small free **Cloudflare Worker** that GitHub deploys for you. The worker holds your Anthropic API key, so the key is never inside the phone app.

Without the worker, the Idea Check tab still works in a simpler mode: it searches Europe PMC directly and lists related papers, with no AI report.

**Cost:** each check makes two Claude calls, roughly $0.05 to $0.15 per check (an estimate, not measured). The worker allows 10 checks per hour per person, and a monthly spend limit on your Anthropic key (console.anthropic.com → Billing → Limits) is your safety net.

---

## 1. Create a free Cloudflare account (5 min)

1. Sign up at **dash.cloudflare.com/sign-up**.
2. In the left menu open **Compute (Workers)** → **Workers & Pages**. If asked, choose a **workers.dev subdomain** (for example your name). Your checker will live at `https://scidigest-idea-checker.<subdomain>.workers.dev`.
3. Copy your **Account ID**: it's shown on the Workers & Pages overview page (right side), or under **Account home → ⋯ next to your account → Copy account ID**.

## 2. Make a Cloudflare API token (3 min)

1. Top right profile icon → **My Profile** → **API Tokens** → **Create Token**.
2. Next to **Edit Cloudflare Workers**, click **Use template**.
3. **Account Resources:** Include → your account. **Zone Resources:** Include → All zones from an account → your account.
4. **Continue to summary** → **Create Token** → copy the token (shown once).

## 3. Get a free OpenAlex key (recommended, 2 min)

OpenAlex is the main paper database the checker searches (about 250 million papers across all fields). Without your own key it shares a tiny daily allowance with everyone else on Cloudflare, so most searches would fail and only Europe PMC would be used.

1. Go to **help.openalex.org/api/authentication** and follow the steps to request a free API key with your email.
2. Copy the key from the email.

## 4. Add the secrets to GitHub

Open **https://github.com/fede4menti-dev/scidigest/settings/secrets/actions** and add (**New repository secret** for each):

| Name | Value |
|---|---|
| `CLOUDFLARE_API_TOKEN` | the token from step 2 |
| `CLOUDFLARE_ACCOUNT_ID` | the account ID from step 1 |
| `OPENALEX_API_KEY` | the key from step 3 |
| `IDEA_CHECKER_APP_TOKEN` | *optional:* any long random text, e.g. `k8Qp2vX7mR4tZ9wL`. Only your app (which knows it) can then use the checker. |

`ANTHROPIC_API_KEY` is already there from the daily digest setup and is reused.

## 5. Deploy

1. Go to **Actions** → **Deploy idea checker** → **Run workflow** → **Run workflow**.
2. Wait for the green tick (1 to 2 minutes). It also redeploys by itself whenever the `worker/` code changes.
3. Open the run → **Deploy to Cloudflare Workers** step. Near the end it prints your URL, like `https://scidigest-idea-checker.yourname.workers.dev`.
4. Check it: open `<that URL>/health` in a browser. You should see `{"ok":true,"ai":true,"openalex_key":true}`.

## 6. Connect the website

So everyone who opens your site gets the full Idea Check report:

1. Open **https://github.com/fede4menti-dev/scidigest/settings/variables/actions** → **New repository variable**.
2. Name `IDEA_CHECKER_URL`, value = the address from step 5 (e.g. `https://scidigest-idea-checker.yourname.workers.dev`).
3. Run **Actions → Daily digest → Run workflow** once so the site picks it up (or wait for tomorrow's run).

Or, just for yourself: on the website open **Settings → Idea checker** and paste the address.

If you set an `IDEA_CHECKER_APP_TOKEN`, the website can't keep it secret, so visitors would need to enter it in Settings. For a public site, leave the token unset and rely on the per-person hourly limit and your Anthropic spend limit.

## 7. Connect the app

Either:

- **In the app:** Settings tab → **Idea checker** → paste the URL (and the app token if you set one), or
- **Before building in Xcode:** put them in `Config.swift` (`defaultIdeaCheckerURL`, `defaultIdeaCheckerToken`) so they're built in. Do this before uploading to TestFlight or the App Store, so testers and reviewers get the full feature.

Then open **Idea Check**, type a question, and tap **Check my idea**. A report takes about 30 to 60 seconds.

## Troubleshooting

| Problem | Fix |
|---|---|
| Deploy fails: "Add the CLOUDFLARE_API_TOKEN..." | Step 4 secrets missing or misnamed. |
| Deploy fails with an authentication error | Recreate the token with the **Edit Cloudflare Workers** template (step 2). |
| `/health` shows `"ai":false` | The `ANTHROPIC_API_KEY` GitHub secret is missing; rerun the deploy after adding it. |
| App says "Not authorised" | The app token in Settings doesn't match `IDEA_CHECKER_APP_TOKEN`. |
| Reports only cite Europe PMC papers | Add `OPENALEX_API_KEY` (step 3) and redeploy. |
