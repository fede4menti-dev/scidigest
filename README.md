# SciDigest

A daily report of the most significant new scientific research. Each morning it:

1. **Scans** the latest research from Nature, Science, Cell, PNAS, NEJM, The Lancet, Nature Communications, Science Advances, Physical Review Letters, eLife, PLOS Biology and several Nature field journals (list in `scidigest/sources.py`). News, corrections, editorials and opinion pieces are filtered out.
2. **Ranks** them by significance with Claude (size of the advance, how broadly it matters, strength of evidence, novelty), keeping a mix of fields.
3. **Looks up citation details** (full author list, volume, pages, abstract) from Crossref using each paper's DOI.
4. **Finds a free, legal full-text copy** when one exists (see below), so summaries can use the real methods and results instead of just the abstract.
5. **Paraphrases** each paper for an average undergrad science student: plain headline, summary, why it matters, caveats, and a mini glossary of key terms. It only uses facts from the abstract, and an automatic check rewrites any summary that copies too much original wording.
6. **Writes the report** as HTML and Markdown, with numbered in-text citations, a source link on every item and an APA-style reference list.

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
| `--hours H` | 36 | how far back to look |
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
- Tests run offline: `pip install pytest && python -m pytest tests`
