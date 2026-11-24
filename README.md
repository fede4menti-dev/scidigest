# SciDigest

A daily report of the most significant new scientific research. Each morning it:

1. **Scans** recent research (the last two weeks, newest preferred) from Nature, Science, Cell, PNAS, NEJM, The Lancet, Nature Communications, Science Advances, Physical Review Letters, eLife, PLOS Biology and several Nature field journals (list in `scidigest/sources.py`). News, corrections, editorials and opinion pieces are filtered out.
2. **Ranks** them by significance with Claude (size of the advance, how broadly it matters, strength of evidence, novelty, and timeliness on the day), keeping a mix of fields. Most picks are new; an older paper can be chosen if it is especially important or relevant that day, and a standout paper can appear on a second day (never more than twice, never on back-to-back days; its earlier summary is reused).
3. **Looks up citation details** (full author list, volume, pages, abstract) from Crossref using each paper's DOI.
4. **Finds a free, legal full-text copy** when one exists (see below), so summaries can use the real methods and results instead of just the abstract.
5. **Paraphrases** each paper for an average undergrad science student: plain headline, summary, why it matters, caveats, and a mini glossary of key terms. It only uses facts from the abstract, and an automatic check rewrites any summary that copies too much original wording.
6. **Writes the report** as HTML and Markdown, with numbered in-text citations, a source link on every item and an APA-style reference list.

## Costs and safeguards

Readers never trigger AI costs by browsing: topics, sorting, saving, searching and accounts work on data that was already generated. AI is used in two places:

| Where | How cost behaves | Built-in savings and limits |
|---|---|---|
| **Daily run** | Fixed per day, the same for 1 reader or 100,000 | Ranking, summaries and reviews go through the **Batches API at half price** (falls back to normal requests for anything refused, failed or unfinished). Full text is sent results-and-conclusions first and capped at 30,000 characters. Reviews only rank the strongest papers. Repeats reuse earlier summaries. Hard cap per run (`SCIDIGEST_MAX_RUN_USD`, default $4): editor's picks first, extra topic picks dropped when reached. Same-day re-runs skipped. The log ends with tokens used and the estimated cost. |
| **Idea Check** | Grows with how many *new* questions people ask | Identical questions answered from a 30-day cache for free; 10 per person per hour; site-wide daily limit (`IDEA_CHECKS_PER_DAY`, default 150); smaller requests (22 papers, short abstracts). Optional: `REQUIRE_ACCOUNT_FOR_CHECKS=1` gives full AI reports only to signed-in readers, with `CHECKS_PER_ACCOUNT_PER_DAY` (default 5) each; signed-out readers still get the free search-only results. |

**Always also set a monthly spend limit on your key:** console.anthropic.com → Billing → Limits.

### Optional switches that trade quality for cost

Set these as repository variables only if you want to spend less and accept somewhat weaker output. Change one at a time and compare a few days of reports.

| Variable | Default | Cheaper option | Effect |
|---|---|---|---|
| `SCIDIGEST_MODEL` | `claude-opus-5-5` | `claude-sonnet-5-5` | About half the price per token for the daily run; summaries and picks may be a little less sharp |
| `SCIDIGEST_SUMMARY_EFFORT` | `medium` | `low` | Less "thinking" per summary, so fewer output tokens; usually fine for plain-language summaries |
| `SCIDIGEST_RANK_EFFORT` | `high` | `medium` | Cheaper daily ranking; for this kind of judgement medium often matches high |
| `SCIDIGEST_PER_TOPIC` | `2` | `1` or `0` | Fewer papers summarised per day (fewer topic picks) |
| `IDEA_CHECK_MODEL` | `claude-opus-5-5` | `claude-sonnet-5-5` | About half the price per idea check |

## Accounts

Readers can create an account in **Settings → Account** (email and password, plus a one-time recovery code). Topics, appearance and reading settings, saved papers, reading history and idea checks then sync across devices. Passwords are stored only as PBKDF2 hashes on the same Cloudflare Worker as the idea checker (Workers KV, created automatically by the deploy workflow). Readers can export their data and delete their account at any time.

## Topics

Every selected paper is assigned to one of 18 topics in 6 groups (Physical Sciences, Math & Computing; Engineering & Technology; Biological & Life Sciences; Health & Medical Sciences; Earth & Environmental Sciences; Society, Policy & Interdisciplinary Studies; full list in `scidigest/taxonomy.py`).

Each day publishes **8 editor's picks** plus **up to 2 of the best papers in every topic** (`--per-topic`, or the `SCIDIGEST_PER_TOPIC` repository variable for the GitHub run). Readers choose their topics in the app and see "For you" papers on every day and review; the website has topic filter chips.

Sources now include about 40 journals (Nature and Science families, Cell, PNAS, NEJM, The Lancet, JAMA, The BMJ, PRL, PLOS, eLife) plus capped arXiv feeds for mathematics, computer science, statistics, economics and robotics. arXiv papers are labelled **Preprint** (not peer reviewed).

**Cost:** each topic pick is one more summary. With 2 per topic expect roughly 25 to 35 summaries a day (an estimate: about $1.50 to $3.50 a day); 1 per topic roughly halves the extra; 0 turns topic picks off.

## Weekly and monthly reviews

When run with `--site`, it also publishes:

- **Weekly review, every Sunday:** the 8 most important papers featured in that week's daily digests, with a short overview of the week.
- **Monthly review, on the 1st:** the same for the whole previous month.

Build one by hand with `python -m scidigest --site docs --review weekly` (or `monthly`). Every paper shows its publication date, and repeats show the other days they were featured.

## Images

Each paper gets an image when one can be shown legally:

- **A figure from the paper** when it's open access under CC BY, CC BY-SA or CC0. Claude picks the figure that best shows the main finding and captions it in plain language.
- **Otherwise an illustrative photo** from Wikimedia Commons under a free licence (public domain, CC0, CC BY, CC BY-SA), labelled "Illustration, not from the paper".

Images under non-commercial or no-derivatives licences are never used, and every image shows credit, licence and a link to its source. Turn images off with `--no-images`.

## Idea checker

The app's **Idea Check** tab tells you whether a research question has already been studied, lists the most important related papers, and reviews the question's clarity, specificity, feasibility, significance and testability. It runs on a free Cloudflare Worker (`worker/`) deployed by GitHub Actions. See **[IDEA-CHECKER-SETUP.md](IDEA-CHECKER-SETUP.md)**.

## iPhone app

See **[IPHONE-SETUP.md](IPHONE-SETUP.md)**: GitHub runs the digest every morning and publishes it, and a SwiftUI app (`ios/SciDigest/`) shows it on your phone.

## Setup

Requires Python 3.10+.

```bash
cd scidigest
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...     # from console.anthropic.com
export SCIDIGEST_EMAIL=you@example.com  # optional: lets it search Unpaywall too
```

## Run it

```bash
python -m scidigest
```

Reports land in `reports/science-digest-YYYY-MM-DD.html` (open in a browser) and `.md`.

Options:

| Flag | Default | What it does |
|---|---|---|
| `--top N` | 8 | papers in the report |
| `--hours H` | 336 | how far back papers can come from (newest preferred) |
| `--review weekly\|monthly` | | only build that review now (needs `--site`) |
| `--no-reviews` | off | skip the automatic Sunday/1st-of-month reviews |
| `--out DIR` | `reports` | output folder |
| `--no-ai` | off | no API key needed; ranks by journal and quotes abstracts instead of paraphrasing |
| `--no-crossref` | off | skip the Crossref metadata lookup |
| `--email ADDR` | `$SCIDIGEST_EMAIL` | contact email Unpaywall asks API users to send |
| `--no-fulltext` | off | summarise from abstracts only |
| `--max-fulltext-chars N` | 150000 | cap on full text sent per paper (about 37K tokens) |

## Free full text

Paywalled papers often have a legal free copy somewhere. For each picked paper, SciDigest checks:

1. **Europe PMC**: open-access full text for papers in PubMed Central (includes NIH-funded research). No setup needed.
2. **Unpaywall**: finds the best legal open-access copy anywhere: the publisher's open-access version, a university repository, or a preprint server like arXiv or bioRxiv. Unpaywall's terms ask for a contact email, so it only runs when `SCIDIGEST_EMAIL` is set. If the copy is a PDF, its text is extracted.

Each paper in the report shows whether it was **summarised from full text or abstract**, and links the free copy labelled as *Published version*, *Author's accepted manuscript (peer reviewed)* or *Preprint (before peer review)*. Preprints can differ from the final paper, and summaries based on one say so. Citations always point to the official published version.

## Run it every day automatically

**macOS / Linux (cron)**: `crontab -e` and add (runs 7:15 every morning):

```
15 7 * * * cd /path/to/scidigest && ANTHROPIC_API_KEY=sk-ant-... SCIDIGEST_EMAIL=you@example.com /usr/bin/python3 -m scidigest >> reports/run.log 2>&1
```

**Windows**: Task Scheduler → Create Basic Task → Daily → Program `python`, arguments `-m scidigest`, start in the `scidigest` folder.

## Customising

- **Add or remove journals**: edit `SOURCES` in `scidigest/sources.py`. Any RSS/Atom feed works; `weight` (0-1) is a rough prior for how significant that journal's papers tend to be.
- **Change the reading level or tone**: edit `SUMMARY_SYSTEM` in `scidigest/ai.py`.
- **Change what "significant" means**: edit `RANK_SYSTEM` in `scidigest/ai.py`.

## Cost

Uses Claude Opus 5.5. A typical day (1 ranking call over ~100 abstracts + 8 summaries) is roughly 60-80K input tokens and 15-25K output tokens, around $0.60-$0.80 per report with abstracts only. Full text adds roughly 10-20K input tokens per paper that has one, so expect about $0.80-$1.50 per report. Use `--no-fulltext` or a lower `--max-fulltext-chars` to keep it cheaper.

## Good to know

- Only legal open-access copies are used. When none exists, the summary is based on the abstract, and the report says so. Always read the original before citing it in your own work.
- Some publishers occasionally rate-limit or change feed URLs; a failing feed is skipped and logged, it won't break the report.
- Tests run offline: `pip install pytest && python -m pytest tests`, and for the worker `cd worker && npm ci && npm test`
