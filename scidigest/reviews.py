"""Weekly (every Sunday) and monthly (on the 1st, for the month before) reviews.

A review re-ranks every paper that appeared in the daily digests during the period and keeps
the most important ones, reusing their existing summaries, plus a short AI-written overview."""
from __future__ import annotations

import copy
from datetime import date, timedelta

from .publish import FORMAT_VERSION, _now, load_dailies, paper_key
from .report import period_label


def weekly_period(end: date) -> tuple[date, date]:
    return end - timedelta(days=6), end


def monthly_period(run_day: date) -> tuple[date, date]:
    """The calendar month before run_day's month."""
    end = run_day.replace(day=1) - timedelta(days=1)
    return end.replace(day=1), end


def due_reviews(today: date) -> list[str]:
    due = []
    if today.weekday() == 6:      # Sunday
        due.append("weekly")
    if today.day == 1:
        due.append("monthly")
    return due


def build_review(site, kind: str, today: date, top: int, use_ai: bool, log=print) -> dict | None:
    if kind == "weekly":
        start, end = weekly_period(today)
        ident = f"weekly-{end.isoformat()}"
        title = f"Weekly Review: {period_label(start, end)}"
        span = "week"
    elif kind == "monthly":
        start, end = monthly_period(today)
        ident = f"monthly-{start:%Y-%m}"
        title = f"Monthly Review: {start:%B %Y}"
        span = "month"
    else:
        raise ValueError(kind)

    # Every paper featured in a daily digest during the period, once, with all its dates.
    pool: dict[str, dict] = {}
    journals: set[str] = set()
    ai_written = True
    for d in load_dailies(site):
        if not (start.isoformat() <= d["date"] <= end.isoformat()):
            continue
        journals.update(d.get("journals", []))
        ai_written = ai_written and d.get("ai_summaries", False)
        for p in d["papers"]:
            k = paper_key(p.get("doi"), p.get("url"), p.get("original_title", ""))
            entry = pool.setdefault(k, {"paper": copy.deepcopy(p), "dates": []})
            entry["dates"].append(d["date"])
            entry["paper"]["significance"] = max(entry["paper"]["significance"], p["significance"])
    if not pool:
        log(f"  no daily digests between {start} and {end}; skipping the {span}ly review")
        return None

    papers = []
    for entry in pool.values():
        p = entry["paper"]
        p["featured_on"] = sorted(set(entry["dates"]))
        papers.append(p)

    if use_ai:
        from . import ai
        label = f"{start:%B %d} to {end:%B %d, %Y}"
        intro, picks = ai.rank_review(papers, top, span, label)
    else:
        intro = ""
        ranked = sorted(papers, key=lambda p: p["significance"], reverse=True)[:top]
        picks = [(p, {"score": p["significance"], "reason": p.get("reason", "")}) for p in ranked]

    chosen = []
    for n, (p, pick) in enumerate(picks, start=1):
        p = copy.deepcopy(p)
        p["rank"] = n
        p["significance"] = int(pick.get("score") or p["significance"])
        p["reason"] = pick.get("reason") or p.get("reason", "")
        chosen.append(p)

    return {
        "format": FORMAT_VERSION,
        "kind": kind,
        "id": ident,
        "title": title,
        "date": end.isoformat(),
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "generated_at": _now(),
        "scanned": len(papers),
        "journals": sorted(journals),
        "ai_summaries": ai_written,   # are the summaries AI paraphrases (they come from the dailies)
        "intro": intro,
        "papers": chosen,
    }
