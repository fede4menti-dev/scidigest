"""Images for papers, using only content we are allowed to show.

1. A figure from the paper itself, when the paper is open access under a reuse licence
   (CC BY, CC BY-SA or CC0). Figures come from Europe PMC's open-access full text.
2. Otherwise an illustrative photo from Wikimedia Commons under a free licence
   (public domain, CC0, CC BY, CC BY-SA), clearly labelled as not from the paper.

Every image carries credit, licence and a link to its source.
"""
from __future__ import annotations

import html
import re
import time

import requests

USER_AGENT = "SciDigest/1.0 (open-source science digest; image lookup)"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"

_REUSABLE = re.compile(r"^\s*(cc[\s-]*by(?![\s-]*n[cd])([\s-]*sa)?\b|cc0|cc[\s-]*zero|public\s+domain|pd\b|pdm)", re.I)
_EMAIL = re.compile(r"\S+@\S+")


def reusable(license_name: str | None) -> bool:
    """True for licences that allow showing the image with credit (no NC/ND restrictions)."""
    return bool(license_name and _REUSABLE.match(license_name))


def _text(value: str, limit: int = 120) -> str:
    t = re.sub(r"<[^>]+>", " ", value or "")
    t = _EMAIL.sub("", html.unescape(t))
    t = re.split(r"\b(Provider Email|Photo Credit|Content Providers?\(s\))\b", t)[0] or t
    t = re.sub(r"\s+", " ", t).strip(" :;,-")
    return t[:limit].rstrip() + ("…" if len(t) > limit else "")


# ------------------------------------------------------------ paper figure

def figure_image(fig: dict, journal: str, license_name: str | None, source_url: str, caption: str) -> dict:
    return {
        "kind": "figure",
        "url": fig["url"],
        "caption": caption or fig.get("caption", ""),
        "credit": f"{fig.get('label') or 'Figure'} from the paper, {journal}",
        "license": (license_name or "").upper(),
        "license_url": _license_url(license_name),
        "source_url": source_url,
    }


def _license_url(name: str | None) -> str | None:
    if not name:
        return None
    n = name.lower().replace("-", " ")
    if "cc0" in n or "zero" in n:
        return "https://creativecommons.org/publicdomain/zero/1.0/"
    if "by" in n:
        kind = "by-sa" if "sa" in n.split() else "by"
        return f"https://creativecommons.org/licenses/{kind}/4.0/"
    return None


# ------------------------------------------------------- Wikimedia Commons

def _commons_search(query: str, retries: int = 2) -> dict:
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"{query} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": 12,
        "prop": "imageinfo", "iiprop": "url|mime|size|extmetadata", "iiurlwidth": 960,
    }
    for attempt in range(retries + 1):
        r = requests.get(COMMONS_API, params=params, headers={"User-Agent": USER_AGENT}, timeout=20)
        if r.status_code == 429 and attempt < retries:
            time.sleep(min(int(r.headers.get("retry-after", "10") or 10), 30))
            continue
        r.raise_for_status()
        return r.json()
    return {}


def wikimedia_image(query: str, log=print) -> dict | None:
    """Best freely licensed photo for a short visual query, or None."""
    if not query or not query.strip():
        return None
    try:
        data = _commons_search(query.strip())
    except Exception as exc:
        log(f"  ! Wikimedia image search failed for '{query}': {exc}")
        return None
    pages = sorted(data.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
    for p in pages:
        info = (p.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        lic = meta.get("LicenseShortName", {}).get("value", "")
        if info.get("mime") not in ("image/jpeg", "image/png") or not reusable(lic):
            continue
        if (info.get("width") or 0) < 500:
            continue
        artist = _text(meta.get("Artist", {}).get("value", "")) or "Unknown author"
        desc = _text(meta.get("ImageDescription", {}).get("value", ""), 400)
        if len(desc) > 100 or re.search(r"https?:|direct link|click", desc, re.I):
            desc = query.strip().capitalize()   # descriptions vary a lot; keep only short, clean ones
        url = (info.get("thumburl") or info.get("url") or "").split("?")[0]
        if not url:
            continue
        return {
            "kind": "illustration",
            "url": url,
            "caption": desc,
            "credit": f"{artist}, via Wikimedia Commons",
            "license": lic,
            "license_url": meta.get("LicenseUrl", {}).get("value") or None,
            "source_url": info.get("descriptionurl", ""),
        }
    return None
