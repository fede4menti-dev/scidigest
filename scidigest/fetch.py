"""Pull recent items from journal RSS/Atom feeds and normalise them."""
from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import feedparser
import requests

from .sources import DEFAULT_MAX_ITEMS, NON_RESEARCH_PREFIXES, SOURCES

USER_AGENT = "SciDigest/1.0 (daily research digest; RSS reader)"
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"<>?#]+", re.I)


@dataclass
class Article:
    id: str
    title: str
    journal: str
    link: str
    abstract: str
    published: datetime | None
    authors: list[str] = field(default_factory=list)
    doi: str | None = None
    year: int | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    prior: float = 0.5  # journal weight
    preprint: bool = False


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _date(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)
    for key in ("dc_date", "prism_publicationdate", "prism_coverdate"):
        v = entry.get(key)
        if v:
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00")).astimezone(timezone.utc)
            except ValueError:
                pass
    return None


def _doi(entry) -> str | None:
    for key in ("prism_doi", "dc_identifier", "id", "link"):
        m = DOI_RE.search(str(entry.get(key, "")))
        if m:
            return m.group(0).rstrip(".")
    return None


def _authors(entry) -> list[str]:
    if entry.get("authors"):
        names = [a.get("name", "") for a in entry["authors"]]
    elif entry.get("author"):
        names = [entry["author"]]
    else:
        names = []
    out: list[str] = []
    for n in names:
        out += [p.strip() for p in re.split(r",\s*(?:and\s+)?|\s+and\s+|;", _clean(n)) if p.strip()]
    return out


# Journals whose DOIs reveal the article type. NEJM: oa = original article, ra = review,
# sa = special article; c = letter, e = editorial, p = perspective, etc.
NON_RESEARCH_DOI = re.compile(r"^10\.1056/NEJM(?!oa|ra|sa)", re.I)


RESEARCH_TAGS = {"articles", "article", "research", "research letter", "review", "seminar", "series", "fast track"}


def strip_tag(title: str) -> str:
    return re.sub(r"^\[[^\]]+\]\s*", "", title)


def is_research(title: str, doi: str | None = None) -> bool:
    t = title.lower().strip()
    tag = re.match(r"^\[([^\]]+)\]\s*", t)  # Lancet style: "[Articles] ...", "[Comment] ..."
    if tag:
        if tag.group(1).strip() not in RESEARCH_TAGS:
            return False
        t = t[tag.end():]
    if not t or t.startswith(NON_RESEARCH_PREFIXES):
        return False
    return not (doi and NON_RESEARCH_DOI.match(doi))


def parse_feed(raw: bytes | str, source: dict) -> list[Article]:
    feed = feedparser.parse(raw)
    items = []
    for e in feed.entries:
        title = _clean(e.get("title", ""))
        if not is_research(title, _doi(e)):
            continue
        title = strip_tag(title)
        abstract = _clean(e.get("summary", "") or e.get("description", ""))
        if source.get("preprint"):
            # arXiv: "arXiv:2511.01234v1 Announce Type: new Abstract: ..." - keep only brand-new papers
            m = re.match(r"^arXiv:(\S+?)(v\d+)?\s+Announce Type:\s*(\S+)\s+Abstract:\s*", abstract)
            if m:
                if m.group(3).lower() not in ("new",):
                    continue
                abstract = abstract[m.end():]
        if e.get("content"):
            longer = _clean(e["content"][0].get("value", ""))
            if len(longer) > len(abstract):
                abstract = longer
        pub = _date(e)
        doi = _doi(e)
        if not doi and source.get("preprint"):
            m = re.search(r"arxiv\.org/abs/([\w.\-/]+?)(v\d+)?$", e.get("link", ""))
            if m:
                doi = f"10.48550/arXiv.{m.group(1)}"
        items.append(Article(
            id=doi or e.get("link", title),
            title=title,
            journal=source["journal"],
            link=e.get("link", "") or (f"https://doi.org/{doi}" if doi else ""),
            abstract=abstract,
            published=pub,
            authors=_authors(e),
            doi=doi,
            year=pub.year if pub else None,
            volume=e.get("prism_volume"),
            issue=e.get("prism_number"),
            pages=e.get("prism_startingpage"),
            prior=source.get("weight", 0.5),
            preprint=bool(source.get("preprint")),
        ))
    return items


def fetch_all(hours: int = 36, sources: list[dict] | None = None, log=print) -> list[Article]:
    """Fetch every source; keep research items from the last `hours` hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    seen, results = set(), []
    for src in sources or SOURCES:
        try:
            r = requests.get(src["url"], headers={"User-Agent": USER_AGENT}, timeout=30)
            r.raise_for_status()
            items = parse_feed(r.content, src)
        except Exception as exc:  # one bad feed shouldn't kill the report
            log(f"  ! {src['journal']}: {exc}")
            continue
        fresh = [a for a in items if a.published is None or a.published >= cutoff]
        fresh.sort(key=lambda a: a.published or cutoff, reverse=True)
        fresh = fresh[: src.get("max_items", DEFAULT_MAX_ITEMS)]
        log(f"  {src['journal']}: {len(fresh)} recent research items")
        for a in fresh:
            key = (a.doi or a.title).lower()
            if key not in seen:
                seen.add(key)
                results.append(a)
    return results
