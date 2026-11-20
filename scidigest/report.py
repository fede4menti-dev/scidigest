"""Render the daily report as HTML and Markdown."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import re

from markupsafe import Markup, escape
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .citations import apa

TEMPLATES = Path(__file__).parent / "templates"


def build_entries(picks, summaries, free=None):
    free = free or [None] * len(picks)
    entries = []
    for n, ((article, pick), s, copy) in enumerate(zip(picks, summaries, free), start=1):
        entries.append({
            "n": n,
            "article": article,
            "pick": pick,
            "s": s,
            "free": copy,
            "citation": apa(article),
            "url": f"https://doi.org/{article.doi}" if article.doi else article.link,
        })
    return entries


def render(entries, day: date, out_dir: Path, scanned: int, journals: list[str], ai: bool):
    out_dir.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(TEMPLATES),
                      autoescape=select_autoescape(["html", "html.j2"]))
    env.filters["md_italics"] = lambda t: Markup(re.sub(r"\*(.+?)\*", r"<em>\1</em>", str(escape(t))))
    ctx = dict(entries=entries, day=day, scanned=scanned, journals=journals, ai=ai)
    html_path = out_dir / f"science-digest-{day.isoformat()}.html"
    md_path = out_dir / f"science-digest-{day.isoformat()}.md"
    html_path.write_text(env.get_template("report.html.j2").render(**ctx), encoding="utf-8")
    md_path.write_text(env.get_template("report.md.j2").render(**ctx), encoding="utf-8")
    return html_path, md_path


def _env():
    env = Environment(loader=FileSystemLoader(TEMPLATES),
                      autoescape=select_autoescape(["html", "html.j2"]))
    env.filters["md_italics"] = lambda t: Markup(re.sub(r"\*(.+?)\*", r"<em>\1</em>", str(escape(t))))
    return env


def html_from_json(digest: dict) -> str:
    """Rebuild a day's HTML page from its published JSON (used to fill in missing pages)."""
    from types import SimpleNamespace as NS
    entries = []
    for p in digest["papers"]:
        free = p.get("free_copy")
        entries.append({
            "n": p["rank"],
            "article": NS(title=p["original_title"], journal=p["journal"]),
            "pick": {"field": p["field"], "score": p["significance"], "reason": p.get("reason", "")},
            "s": {"headline": p["headline"], "summary": p["summary"], "why_it_matters": p["why_it_matters"],
                  "limitations": p.get("limitations", ""), "key_terms": p.get("key_terms", []),
                  "based_on": p.get("based_on", "abstract")},
            "free": NS(**free) if free else None,
            "citation": p["citation"],
            "url": p["url"],
        })
    day = date.fromisoformat(digest["date"])
    return _env().get_template("report.html.j2").render(
        entries=entries, day=day, scanned=digest["scanned"], journals=digest["journals"],
        ai=digest["ai_summaries"])
