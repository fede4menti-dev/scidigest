"""Find legal free (open-access) copies of papers and extract their text.

Order of attempts for each paper with a DOI:
  1. Europe PMC: full text XML for papers in PubMed Central / Europe PMC (no key or email needed).
  2. Unpaywall: finds the best legal open-access copy anywhere (publisher site, repository,
     preprint server). Needs a contact email (SCIDIGEST_EMAIL or --email), per Unpaywall's terms.
     If that copy is a PDF, its text is extracted with pypdf.
If nothing works the paper is summarised from its abstract, as before.
"""
from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import requests

from .fetch import USER_AGENT, Article, _clean

EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
MAX_PDF_BYTES = 25 * 1024 * 1024

VERSION_LABELS = {
    "publishedVersion": "Published version",
    "acceptedVersion": "Author's accepted manuscript (peer reviewed)",
    "submittedVersion": "Preprint (before peer review)",
}

# Sections that add length but little for a student summary.
SKIP_SECTIONS = re.compile(
    r"^(references|acknowledg|author contributions|competing interests|data availability|"
    r"code availability|supplementary|funding|ethics|additional information|extended data)", re.I)


@dataclass
class FreeCopy:
    url: str                    # link shown to the reader
    version: str                # human-readable label
    host: str                   # e.g. "Europe PMC", "repository", "publisher"
    license: str | None = None
    text: str = ""              # extracted full text ("" if only a link was found)


def _get(url: str, **kw) -> requests.Response:
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=kw.pop("timeout", 30), **kw)
    r.raise_for_status()
    return r


# ------------------------------------------------------------- Europe PMC

def jats_to_text(xml: bytes | str) -> str:
    """Pull readable section text out of a JATS full-text XML document."""
    root = ET.fromstring(xml)
    out: list[str] = []
    abstract = root.find(".//front//abstract")
    if abstract is not None:
        out.append("ABSTRACT\n" + _clean(" ".join(abstract.itertext())))
    body = root.find(".//body")
    if body is None:
        return "\n\n".join(out)

    def walk(sec, depth=0):
        title_el = sec.find("title")
        title = _clean(" ".join(title_el.itertext())) if title_el is not None else ""
        if title and SKIP_SECTIONS.match(title):
            return
        if title:
            out.append(("#" * (depth + 1)) + " " + title.upper() if depth == 0 else title)
        for child in sec:
            if child.tag == "p":
                out.append(_clean(" ".join(child.itertext())))
            elif child.tag == "sec":
                walk(child, depth + 1)
            elif child.tag in ("fig", "table-wrap"):
                cap = child.find(".//caption")
                if cap is not None:
                    out.append("[Figure/table caption] " + _clean(" ".join(cap.itertext())))

    walk(body)
    return "\n\n".join(p for p in out if p)


def from_europe_pmc(doi: str) -> tuple[FreeCopy | None, str]:
    """Returns (free copy with text, or None; abstract from Europe PMC, or "")."""
    r = _get(f"{EPMC}/search", params={
        "query": f'DOI:"{doi}"', "format": "json", "resultType": "core", "pageSize": 1})
    results = r.json().get("resultList", {}).get("result", [])
    if not results:
        return None, ""
    rec = results[0]
    abstract = _clean(rec.get("abstractText", ""))
    pmcid = rec.get("pmcid")
    if not pmcid or rec.get("isOpenAccess") != "Y":
        return None, abstract
    text = jats_to_text(_get(f"{EPMC}/{pmcid}/fullTextXML").content)
    if len(text) < 1500:
        return None, abstract
    return FreeCopy(
        url=f"https://europepmc.org/article/PMC/{pmcid}",
        version="Published version" if rec.get("pubType", "").lower() != "preprint"
        else VERSION_LABELS["submittedVersion"],
        host="Europe PMC",
        license=rec.get("license"),
        text=text,
    ), abstract


# --------------------------------------------------------------- Unpaywall

def pdf_to_text(data: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    pages = [(p.extract_text() or "") for p in reader.pages]
    text = "\n".join(pages)
    # Drop the reference list, which is usually last and very long.
    m = re.search(r"\n\s*(References|REFERENCES|Bibliography)\s*\n", text)
    if m and m.start() > len(text) * 0.4:
        text = text[: m.start()]
    return re.sub(r"[ \t]+", " ", text).strip()


def from_unpaywall(doi: str, email: str) -> FreeCopy | None:
    data = _get(f"https://api.unpaywall.org/v2/{doi}", params={"email": email}).json()
    loc = data.get("best_oa_location") if data.get("is_oa") else None
    if not loc:
        return None
    copy = FreeCopy(
        url=loc.get("url_for_landing_page") or loc.get("url") or loc.get("url_for_pdf"),
        version=VERSION_LABELS.get(loc.get("version"), "Open-access copy"),
        host=loc.get("host_type") or "open access",
        license=loc.get("license"),
    )
    pdf_url = loc.get("url_for_pdf")
    if pdf_url:
        try:
            r = _get(pdf_url, timeout=60, stream=True)
            if "pdf" in r.headers.get("Content-Type", "").lower():
                data = r.raw.read(MAX_PDF_BYTES + 1, decode_content=True)
                if len(data) <= MAX_PDF_BYTES:
                    text = pdf_to_text(data)
                    if len(text) >= 1500:
                        copy.text = text
        except Exception:
            pass  # still worth showing the link
    return copy


# ------------------------------------------------------------------ public

def find_free_copy(article: Article, email: str | None, log=print) -> FreeCopy | None:
    if not article.doi:
        return None
    copy = None
    try:
        copy, epmc_abstract = from_europe_pmc(article.doi)
        if len(epmc_abstract) > len(article.abstract):
            article.abstract = epmc_abstract
    except Exception as exc:
        log(f"  ! Europe PMC lookup failed for {article.doi}: {exc}")
    if copy is None and email:
        try:
            copy = from_unpaywall(article.doi, email)
        except Exception as exc:
            log(f"  ! Unpaywall lookup failed for {article.doi}: {exc}")
    return copy
