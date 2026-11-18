"""Command line entry point:  python -m scidigest [options]"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from . import ai
from .citations import enrich
from .fetch import fetch_all, parse_feed
from .fulltext import find_free_copy
from .publish import day_json, publish
from .report import build_entries, render
from .sources import SOURCES


def heuristic_rank(articles, top):
    """No-AI fallback: journal weight, plus a bump for having a real abstract."""
    scored = sorted(articles, key=lambda a: a.prior + min(len(a.abstract), 1200) / 4000, reverse=True)
    return [(a, {"score": round(a.prior * 10), "field": a.journal, "reason": ""}) for a in scored[:top]]


def quoted_summary(a):
    return {"headline": a.title, "summary": a.abstract or "(No abstract in the feed.)",
            "why_it_matters": "Not available without AI mode.", "key_terms": [], "limitations": ""}


def main(argv=None):
    p = argparse.ArgumentParser(prog="scidigest", description="Daily digest of significant new research.")
    p.add_argument("--top", type=int, default=8, help="number of papers in the report (default 8)")
    p.add_argument("--hours", type=int, default=36, help="how far back to look (default 36)")
    p.add_argument("--out", type=Path, default=Path("reports"), help="output folder")
    p.add_argument("--no-ai", action="store_true", help="skip Claude; quote abstracts instead of paraphrasing")
    p.add_argument("--no-crossref", action="store_true", help="skip Crossref metadata lookup")
    p.add_argument("--email", default=os.environ.get("SCIDIGEST_EMAIL"),
                   help="your contact email for Unpaywall (or set SCIDIGEST_EMAIL)")
    p.add_argument("--no-fulltext", action="store_true", help="don't look for free full-text copies")
    p.add_argument("--max-fulltext-chars", type=int, default=150_000,
                   help="cap on full-text characters sent per paper (default 150000, about 37K tokens)")
    p.add_argument("--site", type=Path, help="also publish JSON + HTML for the iPhone app into this folder")
    p.add_argument("--feed-file", nargs=2, action="append", metavar=("JOURNAL", "PATH"),
                   help="read a saved feed file instead of the web (repeatable; for testing)")
    p.add_argument("--max-candidates", type=int, default=120,
                   help="cap on papers sent to the AI ranker (highest journal weight first)")
    args = p.parse_args(argv)

    use_ai = not args.no_ai
    if use_ai and not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        sys.exit("No ANTHROPIC_API_KEY set. Export one, or run with --no-ai.")

    print("Scanning journals...")
    if args.feed_file:
        weights = {s["journal"]: s["weight"] for s in SOURCES}
        articles = []
        for journal, path in args.feed_file:
            articles += parse_feed(Path(path).read_bytes(), {"journal": journal, "weight": weights.get(journal, 0.6)})
    else:
        articles = fetch_all(hours=args.hours)
    if not articles:
        sys.exit("No new research articles found. Try a larger --hours window.")
    journals = sorted({a.journal for a in articles})
    print(f"Found {len(articles)} research articles in {len(journals)} journals.")

    candidates = sorted(articles, key=lambda a: a.prior, reverse=True)[: args.max_candidates]
    if use_ai:
        print("Ranking by significance with Claude...")
        picks = ai.rank(candidates, args.top)
    else:
        picks = heuristic_rank(candidates, args.top)

    if not args.no_crossref:
        print("Looking up citation details on Crossref...")
        for a, _ in picks:
            enrich(a)

    free = [None] * len(picks)
    if not args.no_fulltext:
        print("Looking for free, legal full-text copies (Europe PMC" + (", Unpaywall" if args.email else "") + ")...")
        if not args.email:
            print("  (set SCIDIGEST_EMAIL or --email to also search Unpaywall)")
        free = [find_free_copy(a, args.email) for a, _ in picks]
        print(f"  full text found for {sum(1 for c in free if c and c.text)} of {len(picks)}; "
              f"free link for {sum(1 for c in free if c)} of {len(picks)}")

    if use_ai:
        print(f"Writing {len(picks)} student-level summaries...")
        jobs = [(a, c.text if c else "", c.version if c else "") for (a, _), c in zip(picks, free)]
        summaries = ai.summarize_many(jobs, max_chars=args.max_fulltext_chars)
    else:
        summaries = [quoted_summary(a) for a, _ in picks]

    entries = build_entries(picks, summaries, free)
    html_path, md_path = render(entries, date.today(), args.out, len(articles), journals, use_ai)
    print(f"\nDone.\n  HTML:     {html_path.resolve()}\n  Markdown: {md_path.resolve()}")
    if args.site:
        digest = day_json(entries, date.today(), len(articles), journals, use_ai)
        print(f"  App data: {publish(args.site, digest, html_path).resolve()}")


if __name__ == "__main__":
    main()
