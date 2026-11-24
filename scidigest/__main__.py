"""Command line entry point:  python -m scidigest [options]"""
from __future__ import annotations

import argparse
import json
import time
import os
import sys
from datetime import date
from pathlib import Path

from . import ai
from .citations import enrich
from .fetch import fetch_all, parse_feed
from .fulltext import europe_pmc_abstract, find_free_copy
from concurrent.futures import ThreadPoolExecutor
from .fulltext import FreeCopy
from .images import figure_image, wikimedia_image
from .backfill import audit_images, backfill_images, backfill_topics
from .publish import day_json, featured_history, paper_key, publish, rebuild_site
from .report import build_entries, render
from .reviews import build_review, due_reviews
from .sources import SOURCES


MIN_ABSTRACT = 300  # characters; shorter means the feed gave a teaser or just citation details


def fill_abstracts(articles, use_crossref=True, workers=8):
    """Look up missing or very short abstracts (Crossref, then Europe PMC) so papers are ranked on substance."""
    def fill(a):
        if len(a.abstract) >= MIN_ABSTRACT or not a.doi:
            return
        if use_crossref:
            enrich(a)
        if len(a.abstract) < MIN_ABSTRACT:
            try:
                alt = europe_pmc_abstract(a.doi)
                if len(alt) > len(a.abstract):
                    a.abstract = alt
            except Exception:
                pass
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(fill, articles))


def heuristic_rank(articles, top):
    """No-AI fallback: journal weight, plus a bump for having a real abstract. No topics."""
    scored = sorted(articles, key=lambda a: a.prior + min(len(a.abstract), 1200) / 4000, reverse=True)
    return [(a, {"score": round(a.prior * 10), "field": a.journal, "reason": "", "topic": None,
                 "editors_pick": True}) for a in scored[:top]]


def quoted_summary(a):
    """Used without AI, or when the spending cap is reached: a short excerpt only, never the full abstract."""
    return {"headline": a.title, "summary": ai.abstract_excerpt(a.abstract),
            "why_it_matters": "A plain-language summary isn't available for this paper. Above is a short excerpt "
                              "of the publisher's abstract; read the full paper via the link below.",
            "key_terms": [], "limitations": ""}


MAX_APPEARANCES = 2     # a paper can be a daily pick on at most two days
MIN_REPEAT_GAP = 3      # ...and not again within 3 days (so never on back-to-back days)


def freshness(a, today) -> float:
    if not a.published:
        return 0.2
    age = (today - a.published.date()).days
    return 0.6 if age <= 2 else 0.3 if age <= 7 else 0.0


def summary_from_paper(p: dict) -> dict:
    return {"headline": p["headline"], "summary": p["summary"], "why_it_matters": p["why_it_matters"],
            "limitations": p.get("limitations", ""), "key_terms": p.get("key_terms", []),
            "based_on": p.get("based_on", "abstract"), "image": p.get("image")}


def pick_image(article, summary: dict, copy) -> dict | None:
    """The chosen open-access figure if allowed, else a free-licensed Wikimedia photo."""
    i = summary.get("figure_index", -1)
    figs = copy.figures if copy else []
    if isinstance(i, int) and 0 <= i < len(figs):
        return figure_image(figs[i], article.journal, copy.license, copy.url, summary.get("figure_caption", ""))
    field = (summary.get("field") or getattr(article, "field", "") or "")
    return wikimedia_image(summary.get("image_query", ""), fallback=field)


def main(argv=None):
    p = argparse.ArgumentParser(prog="scidigest", description="Daily digest of significant new research.")
    p.add_argument("--top", type=int, default=8, help="number of editor's picks per report (default 8)")
    p.add_argument("--per-topic", type=int, default=int(os.environ.get("SCIDIGEST_PER_TOPIC", "2")),
                   help="extra best papers per topic for readers who filter by topic (default 2; 0 = off). "
                        "Each one adds a summary, so this is the main cost lever.")
    p.add_argument("--hours", type=int, default=336,
                   help="how far back papers can come from (default 336 = 14 days; newest are preferred)")
    p.add_argument("--out", type=Path, default=Path("reports"), help="output folder")
    p.add_argument("--no-ai", action="store_true", help="skip Claude; quote abstracts instead of paraphrasing")
    p.add_argument("--no-crossref", action="store_true", help="skip Crossref metadata lookup")
    p.add_argument("--email", default=os.environ.get("SCIDIGEST_EMAIL"),
                   help="your contact email for Unpaywall (or set SCIDIGEST_EMAIL)")
    p.add_argument("--no-fulltext", action="store_true", help="don't look for free full-text copies")
    p.add_argument("--max-fulltext-chars", type=int, default=30_000,
                   help="cap on full-text characters sent per paper (default 30000, about 8K tokens; "
                        "results and conclusions are placed first, so the cut trims methods detail)")
    p.add_argument("--no-batch", action="store_true",
                   help="use normal API requests instead of the half-price Batches API")
    p.add_argument("--no-images", action="store_true", help="don't add figures or illustrative photos")
    p.add_argument("--site", type=Path, help="also publish JSON + HTML for the iPhone app into this folder")
    p.add_argument("--review", choices=["weekly", "monthly"],
                   help="only build this review now (needs --site with past daily digests)")
    p.add_argument("--no-reviews", action="store_true",
                   help="don't build the automatic Sunday weekly / 1st-of-month monthly reviews")
    p.add_argument("--force", action="store_true", help="rebuild today's digest even if it already exists")
    p.add_argument("--today", type=date.fromisoformat, default=None, help=argparse.SUPPRESS)
    p.add_argument("--feed-file", nargs=2, action="append", metavar=("JOURNAL", "PATH"),
                   help="read a saved feed file instead of the web (repeatable; for testing)")
    p.add_argument("--max-candidates", type=int, default=300,
                   help="cap on papers sent to the AI ranker (freshest and best journals first)")
    args = p.parse_args(argv)

    today = args.today or date.today()
    if args.no_batch:
        os.environ["SCIDIGEST_BATCH"] = "0"
    use_ai = not args.no_ai
    if use_ai and not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        sys.exit("No ANTHROPIC_API_KEY set. Export one, or run with --no-ai.")

    if args.review:
        if not args.site:
            sys.exit("--review needs --site (the folder with past daily digests).")
        backfill_topics(args.site, use_ai)
        make_review(args, args.review, today, use_ai)
        return

    existing = args.site / "data" / f"{today.isoformat()}.json" if args.site else None
    if existing and existing.exists() and not args.force and not args.feed_file:
        try:
            done_today = json.loads(existing.read_text(encoding="utf-8")).get("ai_summaries")
        except ValueError:
            done_today = False
        if done_today or not use_ai:
            print(f"Today's digest ({today}) already exists; skipping to avoid paying twice. Use --force to rebuild it.")
            if not args.no_images and not args.feed_file:
                audit_images(args.site)      # no AI: drop photos that break the content rules
                backfill_images(args.site)   # no AI: fix image links, fill missing photos
            rebuild_site(args.site)   # still refresh the pages (new settings, idea checker address); no AI used
            print("Pages refreshed.")
            if args.site and not args.no_reviews:
                for kind in due_reviews(today):
                    make_review(args, kind, today, use_ai)
            return

    print("Scanning journals...")
    if args.feed_file:
        weights = {s["journal"]: s["weight"] for s in SOURCES}
        articles = []
        for journal, path in args.feed_file:
            articles += parse_feed(Path(path).read_bytes(), {"journal": journal, "weight": weights.get(journal, 0.6)})
    else:
        articles = fetch_all(hours=args.hours)
    if not articles:
        sys.exit("No recent research articles found. Try a larger --hours window.")
    journals = sorted({a.journal for a in articles})
    print(f"Found {len(articles)} research articles in {len(journals)} journals.")

    # What earlier daily digests already featured (ignoring today's, so a rerun can pick the same).
    history = {k: h for k, h in featured_history(args.site).items()}
    for h in history.values():
        h["dates"] = [d for d in h["dates"] if d != today.isoformat()]
    history = {k: h for k, h in history.items() if h["dates"]}

    def key(a):
        return paper_key(a.doi, a.link, a.title)

    def allowed(a):
        h = history.get(key(a))
        if not h:
            return True
        last = max(date.fromisoformat(d) for d in h["dates"])
        return len(h["dates"]) < MAX_APPEARANCES and (today - last).days >= MIN_REPEAT_GAP

    candidates = [a for a in articles if allowed(a)]
    candidates.sort(key=lambda a: a.prior + freshness(a, today), reverse=True)
    candidates = candidates[: args.max_candidates]
    if not args.feed_file:
        short = sum(1 for a in candidates if len(a.abstract) < MIN_ABSTRACT)
        if short:
            print(f"Looking up abstracts for {short} papers whose feed had none...")
            fill_abstracts(candidates, use_crossref=not args.no_crossref)
    with_abstract = [a for a in candidates if len(a.abstract) >= MIN_ABSTRACT]
    if len(with_abstract) >= args.top:
        dropped = len(candidates) - len(with_abstract)
        if dropped:
            print(f"  skipping {dropped} papers with no usable abstract")
        candidates = with_abstract

    if not candidates:
        print("No eligible papers today (all were featured recently); skipping the daily digest.")
        if args.site and not args.no_reviews:
            for kind in due_reviews(today):
                make_review(args, kind, today, use_ai)
        return

    featured = {i: history[key(a)]["dates"] for i, a in enumerate(candidates) if key(a) in history}
    if use_ai:
        print(f"Ranking {len(candidates)} papers by significance with Claude...")
        picks = ai.rank(candidates, args.top, today=today, featured=featured, per_topic=args.per_topic)
        n_ed = sum(1 for _, p in picks if p.get("editors_pick"))
        print(f"  {n_ed} editor's picks + {len(picks) - n_ed} topic picks across "
              f"{len({p.get('topic') for _, p in picks})} topics")
    else:
        picks = heuristic_rank(candidates, args.top)

    repeats = {i for i, (a, _) in enumerate(picks) if key(a) in history}
    new = [i for i in range(len(picks)) if i not in repeats]
    if repeats:
        print(f"  {len(repeats)} pick(s) featured before; reusing their summaries")

    if not args.no_crossref:
        print("Looking up citation details on Crossref...")
        for i in new:
            enrich(picks[i][0])

    free = [None] * len(picks)
    for i in repeats:
        fc = history[key(picks[i][0])]["paper"].get("free_copy")
        free[i] = FreeCopy(**fc) if fc else None
    if not args.no_fulltext and new:
        print("Looking for free, legal full-text copies (Europe PMC" + (", Unpaywall" if args.email else "") + ")...")
        if not args.email:
            print("  (set SCIDIGEST_EMAIL or --email to also search Unpaywall)")
        for i in new:
            free[i] = find_free_copy(picks[i][0], args.email)
        found = [free[i] for i in new]
        print(f"  full text found for {sum(1 for c in found if c and c.text)} of {len(new)}; "
              f"free link for {sum(1 for c in found if c)} of {len(new)}")

    summaries = [None] * len(picks)
    for i in repeats:
        summaries[i] = summary_from_paper(history[key(picks[i][0])]["paper"])
    if use_ai and new:
        print(f"Writing {len(new)} student-level summaries (editor's picks first)...")
        jobs = [(picks[i][0], free[i].text if free[i] else "", free[i].version if free[i] else "",
                 free[i].figures if free[i] else []) for i in new]
        for i, s in zip(new, ai.summarize_many(jobs, max_chars=args.max_fulltext_chars)):
            summaries[i] = s
        skipped = [i for i in new if summaries[i] is None]
        if skipped:
            print(f"  ! spending cap reached: {len(skipped)} paper(s) not summarised")
            for i in skipped:
                if picks[i][1].get("editors_pick"):
                    summaries[i] = quoted_summary(picks[i][0])   # keep editor's picks, quoting the abstract
            keep = [i for i in range(len(picks)) if summaries[i] is not None]
            picks, summaries, free = [picks[i] for i in keep], [summaries[i] for i in keep], [free[i] for i in keep]
            new = [keep.index(i) for i in new if i in keep]
            repeats = {keep.index(i) for i in repeats if i in keep}
        if not args.no_images:
            print("Finding images (open-access figures, else free-licensed photos)...")
            for i in new:
                summaries[i]["image"] = pick_image(picks[i][0], summaries[i], free[i])
                time.sleep(0.5)  # be polite to Wikimedia's API
            print(f"  images for {sum(1 for i in new if summaries[i].get('image'))} of {len(new)} papers")
    elif new:
        for i in new:
            summaries[i] = quoted_summary(picks[i][0])

    before = [sorted(history[key(a)]["dates"]) if key(a) in history else [] for a, _ in picks]
    entries = build_entries(picks, summaries, free, before)
    for i in repeats:  # keep the citation exactly as it was first published
        old = history[key(picks[i][0])]["paper"]
        entries[i]["citation"], entries[i]["url"] = old["citation"], old["url"]

    digest = day_json(entries, today, len(articles), journals, use_ai)
    html_path, md_path = render(digest, args.out)
    print(f"\nDone.\n  HTML:     {html_path.resolve()}\n  Markdown: {md_path.resolve()}")
    if args.site:
        print(f"  App data: {publish(args.site, digest).resolve()}")
        changed = backfill_topics(args.site, use_ai)
        if not args.no_images and not args.feed_file:     # feed files = offline test runs
            changed = audit_images(args.site) or changed
            changed = backfill_images(args.site) or changed
        if changed:
            rebuild_site(args.site)
        if not args.no_reviews:
            for kind in due_reviews(today):
                make_review(args, kind, today, use_ai)


def make_review(args, kind, today, use_ai):
    if use_ai:
        try:
            ai.check_budget()
        except ai.BudgetExceeded:
            print(f"\nSkipping the {kind} review: spending cap reached.")
            return
    print(f"\nBuilding the {kind} review...")
    review = build_review(args.site, kind, today, args.top, use_ai, per_topic=args.per_topic)
    if review is None:
        return
    html_path, _ = render(review, args.out)
    print(f"  {review['title']}: {len(review['papers'])} papers from {review['scanned']} featured")
    print(f"  HTML:     {html_path.resolve()}")
    print(f"  App data: {publish(args.site, review).resolve()}")


def run():
    try:
        main()
        if ai._usage["calls"]:
            print("\n" + ai.usage_line())
    except ai.anthropic.AuthenticationError:
        sys.exit("\nERROR: Anthropic rejected the API key (401). Check the ANTHROPIC_API_KEY secret: it should "
                 "be one line starting with sk-ant-api03-, with no quotes or spaces. Create a new key at "
                 "console.anthropic.com if unsure.")
    except ai.anthropic.PermissionDeniedError:
        sys.exit("\nERROR: the API key is valid but not allowed to use this model (403). Check the key's "
                 "workspace/service-account permissions in console.anthropic.com.")


if __name__ == "__main__":
    run()
