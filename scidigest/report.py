"""Render digests (daily, weekly, monthly) as HTML and Markdown.

Everything is rendered from the digest JSON (see publish.py), so daily pages, review
pages and pages rebuilt later all look the same."""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace as NS

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

from .citations import apa

TEMPLATES = Path(__file__).parent / "templates"


def build_entries(picks, summaries, free=None, featured=None):
    """Combine ranked articles, their summaries and free copies into report entries."""
    free = free or [None] * len(picks)
    featured = featured or [[] for _ in picks]
    entries = []
    for n, ((article, pick), s, copy, before) in enumerate(zip(picks, summaries, free, featured), start=1):
        entries.append({
            "n": n,
            "article": article,
            "pick": pick,
            "s": s,
            "free": copy,
            "featured_on": before,
            "citation": apa(article),
            "url": f"https://doi.org/{article.doi}" if article.doi else article.link,
        })
    return entries


# ------------------------------------------------------------- formatting

def long_date(d: date) -> str:
    return f"{d:%A}, {d:%B} {d.day}, {d.year}"


def short_date(d: date, with_year: bool = True) -> str:
    return f"{d:%b} {d.day}, {d.year}" if with_year else f"{d:%b} {d.day}"


def iso_to_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(s[:10])
        except ValueError:
            return None


def period_label(start: date, end: date) -> str:
    if start.year == end.year:
        return f"{short_date(start, with_year=False)} to {short_date(end)}"
    return f"{short_date(start)} to {short_date(end)}"


def headings(digest: dict) -> tuple[str, str]:
    """(title, subtitle) for the top of a page."""
    kind = digest.get("kind", "daily")
    n = len(digest["papers"])
    if kind == "daily":
        d = date.fromisoformat(digest["date"])
        sub = (f"{long_date(d)} · {n} papers chosen from {digest['scanned']} recent research articles "
               f"in {len(digest['journals'])} journal{'s' if len(digest['journals']) != 1 else ''}")
        return digest.get("title") or "Daily Science Digest", sub
    start, end = date.fromisoformat(digest["period_start"]), date.fromisoformat(digest["period_end"])
    span = "week" if kind == "weekly" else "month"
    when = "" if kind == "weekly" else f"{period_label(start, end)} · "   # weekly titles already show the dates
    sub = (f"{when}The {n} most important papers of the {span}, "
           f"from {digest['scanned']} featured in the daily digests")
    return digest["title"], sub


def _italicize_journal(citation: str, journal: str) -> str:
    i = citation.rfind(journal)  # the journal name comes after the title
    return citation if i < 0 else f"{citation[:i]}*{journal}*{citation[i + len(journal):]}"


def entries_from_json(digest: dict) -> list[dict]:
    is_review = digest.get("kind", "daily") != "daily"
    out = []
    for p in digest["papers"]:
        free = p.get("free_copy")
        pub = iso_to_date(p.get("published"))
        featured = [d for d in (iso_to_date(x) for x in p.get("featured_on") or []) if d]
        if featured:
            dates = ", ".join(short_date(d) for d in featured)
            featured_label = (f"From the daily digest of {dates}" if is_review else f"Also featured on {dates}")
        else:
            featured_label = ""
        out.append({
            "n": p["rank"],
            "article": NS(title=p["original_title"], journal=p["journal"]),
            "pick": {"field": p["field"], "score": p["significance"], "reason": p.get("reason", "")},
            "s": {"headline": p["headline"], "summary": p["summary"], "why_it_matters": p["why_it_matters"],
                  "limitations": p.get("limitations", ""), "key_terms": p.get("key_terms", []),
                  "based_on": p.get("based_on", "abstract")},
            "free": NS(**free) if free else None,
            "citation": _italicize_journal(p["citation"], p["journal"]),
            "url": p["url"],
            "published_label": f"Published {short_date(pub)}" if pub else "Publication date not listed",
            "featured_label": featured_label,
            "image": NS(**p["image"]) if p.get("image") else None,
        })
    return out


def _env() -> Environment:
    env = Environment(loader=FileSystemLoader(TEMPLATES),
                      autoescape=select_autoescape(["html", "html.j2"]))
    env.filters["md_italics"] = lambda t: Markup(re.sub(r"\*(.+?)\*", r"<em>\1</em>", str(escape(t))))
    return env


def _context(digest: dict) -> dict:
    title, subtitle = headings(digest)
    return dict(entries=entries_from_json(digest), title=title, subtitle=subtitle,
                intro=digest.get("intro", ""), ai=digest["ai_summaries"],
                is_review=digest.get("kind", "daily") != "daily")


def html_from_json(digest: dict) -> str:
    return _env().get_template("report.html.j2").render(**_context(digest))


def markdown_from_json(digest: dict) -> str:
    return _env().get_template("report.md.j2").render(**_context(digest))


def render(digest: dict, out_dir: Path) -> tuple[Path, Path]:
    """Write <out>/science-digest-<id>.html and .md for a digest."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = digest.get("id") or digest["date"]
    html_path = out_dir / f"science-digest-{stem}.html"
    md_path = out_dir / f"science-digest-{stem}.md"
    html_path.write_text(html_from_json(digest), encoding="utf-8")
    md_path.write_text(markdown_from_json(digest), encoding="utf-8")
    return html_path, md_path
