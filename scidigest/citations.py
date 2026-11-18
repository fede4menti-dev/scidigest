"""Enrich article metadata from Crossref and format APA-style citations."""
from __future__ import annotations

import requests

from .fetch import USER_AGENT, Article, _clean


def enrich(article: Article, timeout: int = 15) -> Article:
    """Fill authors/volume/pages/abstract from Crossref when a DOI is known."""
    if not article.doi:
        return article
    try:
        r = requests.get(f"https://api.crossref.org/works/{article.doi}",
                         headers={"User-Agent": USER_AGENT}, timeout=timeout)
        r.raise_for_status()
        m = r.json()["message"]
    except Exception:
        return article
    if m.get("author"):
        article.authors = [
            f"{a.get('given', '')} {a.get('family', '')}".strip() or a.get("name", "")
            for a in m["author"]
        ]
    parts = (m.get("published") or m.get("issued") or {}).get("date-parts", [[None]])
    article.year = parts[0][0] or article.year
    article.volume = m.get("volume") or article.volume
    article.issue = m.get("issue") or article.issue
    article.pages = m.get("page") or m.get("article-number") or article.pages
    if m.get("abstract") and len(_clean(m["abstract"])) > len(article.abstract):
        article.abstract = _clean(m["abstract"]).removeprefix("Abstract ").strip()
    return article


def _apa_name(full: str) -> str:
    bits = full.replace(".", ". ").split()
    if len(bits) < 2:
        return full
    family = bits[-1]
    initials = " ".join(f"{b[0]}." for b in bits[:-1] if b[0].isalpha())
    return f"{family}, {initials}"


def apa(article: Article) -> str:
    names = [_apa_name(n) for n in article.authors if n]
    if not names:
        authors = ""
    elif len(names) == 1:
        authors = names[0]
    elif len(names) <= 20:
        authors = ", ".join(names[:-1]) + ", & " + names[-1]
    else:
        authors = ", ".join(names[:19]) + ", ... " + names[-1]
    year = f"({article.year})" if article.year else "(n.d.)"
    title = article.title.rstrip(".")
    src = f"*{article.journal}*"
    if article.volume:
        src += f", *{article.volume}*"
        if article.issue:
            src += f"({article.issue})"
    if article.pages:
        src += f", {article.pages}"
    link = f"https://doi.org/{article.doi}" if article.doi else article.link
    head = f"{authors} {year}." if authors else f"{title}. {year}."
    body = f" {title}. {src}." if authors else f" {src}."
    return f"{head}{body} {link}".strip()
