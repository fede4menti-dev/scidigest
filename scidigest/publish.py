"""Publish digests as a small static site + JSON feed that the iPhone app reads.

Layout under the site folder (served by GitHub Pages):
  index.html                          list of all reports (for browsers)
  privacy.html                        privacy policy (for the App Store)
  reports/<id>.html                   full HTML page for each digest
  data/index.json                     lists of daily, weekly and monthly digests, newest first
  data/latest.json                    copy of the newest daily digest
  data/YYYY-MM-DD.json                a daily digest            (id = the date)
  data/weekly-YYYY-MM-DD.json         a weekly review, ending on that Sunday
  data/monthly-YYYY-MM.json           a monthly review

JSON format version 1 (new fields are additive). ios/SciDigest/Models.swift mirrors these names.
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import date, datetime, timezone
from pathlib import Path

from markupsafe import escape

from .report import _env, headings, html_from_json, long_date, site_context
from .taxonomy import as_json as taxonomy_json, topic_name

FORMAT_VERSION = 1
STATIC = Path(__file__).parent / "static"
DAILY_GLOB = "????-??-??.json"


def _plain(citation: str) -> str:
    return re.sub(r"\*(.+?)\*", r"\1", citation)


def paper_key(doi: str | None, url: str | None, title: str = "") -> str:
    return (doi or url or title).strip().lower()


def paper_json(e: dict) -> dict:
    a, s, pick, free = e["article"], e["s"], e["pick"], e.get("free")
    return {
        "rank": e["n"],
        "headline": s["headline"],
        "original_title": a.title,
        "journal": a.journal,
        "field": pick.get("field") or a.journal,
        "significance": int(pick.get("score") or 0),
        "reason": pick.get("reason", ""),
        "summary": s["summary"],
        "why_it_matters": s["why_it_matters"],
        "limitations": s.get("limitations", ""),
        "key_terms": [{"term": t["term"], "meaning": t["meaning"]} for t in s.get("key_terms", [])],
        "based_on": s.get("based_on", "abstract"),
        "authors": a.authors,
        "published": a.published.isoformat() if a.published else None,
        "doi": a.doi,
        "url": e["url"],
        "citation": _plain(e["citation"]),
        "free_copy": None if not free else {
            "url": free.url, "version": free.version, "host": free.host, "license": free.license,
        },
        "featured_on": list(e.get("featured_on") or []),
        "image": s.get("image"),
        "image_query": s.get("image_query", ""),
        "category": pick.get("topic"),
        "category_name": topic_name(pick.get("topic")),
        "editors_pick": bool(pick.get("editors_pick", True)),
        "preprint": bool(getattr(a, "preprint", False)),
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def day_json(entries, day: date, scanned: int, journals: list[str], ai: bool) -> dict:
    return {
        "format": FORMAT_VERSION,
        "kind": "daily",
        "id": day.isoformat(),
        "title": "Daily Science Digest",
        "date": day.isoformat(),
        "period_start": day.isoformat(),
        "period_end": day.isoformat(),
        "generated_at": _now(),
        "scanned": scanned,
        "journals": journals,
        "ai_summaries": ai,
        "intro": "",
        "papers": [paper_json(e) for e in entries],
    }


def load_dailies(site: Path | None) -> list[dict]:
    """Every published daily digest, oldest first."""
    if not site or not (site / "data").exists():
        return []
    return [json.loads(f.read_text(encoding="utf-8")) for f in sorted((site / "data").glob(DAILY_GLOB))]


def featured_history(site: Path | None) -> dict[str, dict]:
    """paper key -> {"dates": [dates it was a daily pick], "paper": its most recent paper JSON}."""
    hist: dict[str, dict] = {}
    for d in load_dailies(site):
        for p in d["papers"]:
            k = paper_key(p.get("doi"), p.get("url"), p.get("original_title", ""))
            h = hist.setdefault(k, {"dates": [], "paper": p})
            if d["date"] not in h["dates"]:
                h["dates"].append(d["date"])
            h["paper"] = p
    return hist


PRIVACY_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>SciDigest Privacy Policy</title>
<style>body{margin:0;font:17px/1.6 -apple-system,system-ui,sans-serif;background:#fbfaf7;color:#1d1d1f}
@media (prefers-color-scheme:dark){body{background:#141517;color:#ececec}}
main{max-width:700px;margin:0 auto;padding:40px 16px}h2{font-size:1.1rem;margin-top:28px}</style></head><body><main>
<h1>SciDigest Privacy Policy</h1>
<p><strong>SciDigest collects as little as possible. No advertising, no analytics, no tracking, and nothing is sold or shared.</strong></p>
<h2>Without an account</h2>
<ul>
<li>Your settings (topics, appearance, text size), saved papers, reading history and idea checks are stored only on your device
(in your browser, or in the iPhone app).</li>
<li>Reports are downloaded from this website (hosted on GitHub Pages). Like any website, GitHub may keep standard server logs such as IP addresses; see GitHub's privacy statement.</li>
<li>Daily reminders in the iPhone app are local notifications on your device. No push server is used.</li>
</ul>
<h2>With an account (optional)</h2>
<ul>
<li>We store your email address, your password as a one-way secure hash (PBKDF2), a hash of your recovery code, and the data you choose to sync:
topics, appearance and reading settings, saved papers, which papers you opened, and your recent idea checks.</li>
<li>This is stored on Cloudflare (Workers KV) and used only to sync your data between your devices.</li>
<li>You can export your data and delete your account at any time in Settings. Deleting your account removes it and its synced data from the server immediately.</li>
</ul>
<h2>Idea Check</h2>
<ul>
<li>Questions you check are sent to our server, which searches OpenAlex and Europe PMC and asks an AI model (Anthropic's Claude) to write the report.
The question and report are cached for up to 30 days, without any link to who asked, so identical questions are answered instantly.</li>
<li>To prevent abuse, the server counts requests per IP address for up to one hour; this count is not stored.</li>
</ul>
<h2>Links and summaries</h2>
<ul>
<li>Links to papers and images open other websites, which have their own policies.</li>
<li>Summaries are written by an AI model from publicly available abstracts and open-access papers and may contain mistakes. Always check the original paper.</li>
</ul>
<p>Questions or deletion requests: open an issue at github.com/fede4menti-dev/scidigest.</p>
</main></body></html>
"""




def _dump(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def publish(site: Path, digest: dict) -> Path:
    """Write one digest (daily or review) and rebuild the index, pages and listing."""
    (site / "data").mkdir(parents=True, exist_ok=True)
    (site / "reports").mkdir(parents=True, exist_ok=True)
    ident = digest.get("id") or digest["date"]
    _dump(site / "data" / f"{ident}.json", digest)
    (site / "reports" / f"{ident}.html").write_text(html_from_json(digest), encoding="utf-8")
    rebuild_site(site)
    return site / "data" / f"{ident}.json"


def _review_entry(d: dict) -> dict:
    return {"id": d["id"], "kind": d["kind"], "title": d["title"],
            "period_start": d["period_start"], "period_end": d["period_end"],
            "count": len(d["papers"]), "top_headlines": [p["headline"] for p in d["papers"][:3]]}


def search_index(days: list[dict]) -> list[dict]:
    """Compact list of every paper in the daily digests (newest first, each paper once) for site search."""
    from .report import entries_from_json, short_date
    seen, out = set(), []
    for d in days:
        ident = d.get("id") or d["date"]
        for e, p in zip(entries_from_json(d), d["papers"]):
            key = paper_key(p.get("doi"), p.get("url"), p.get("original_title", ""))
            if key in seen:
                continue
            seen.add(key)
            out.append({"k": p["url"], "h": p["headline"], "i": e["intro"], "j": p["journal"],
                        "t": p.get("category") or "", "tn": e["topic_name"], "o": p["original_title"],
                        "d": e["published_label"].replace("Published ", ""), "r": f"reports/{ident}.html#p{p['rank']}",
                        "img": (p.get("image") or {}).get("url", "")})
    return out


def rebuild_site(site: Path) -> None:
    data, reports = site / "data", site / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    digests = {}
    for f in data.glob("*.json"):
        if f.stem in ("index", "latest", "topics", "search"):
            continue
        digests[f.stem] = json.loads(f.read_text(encoding="utf-8"))
        # Re-render every page, so missing pages come back and design changes reach old reports.
        (reports / f"{f.stem}.html").write_text(html_from_json(digests[f.stem]), encoding="utf-8")

    days = sorted((d for k, d in digests.items() if d.get("kind", "daily") == "daily"),
                  key=lambda d: d["date"], reverse=True)
    weekly = sorted((d for d in digests.values() if d.get("kind") == "weekly"),
                    key=lambda d: d["period_end"], reverse=True)
    monthly = sorted((d for d in digests.values() if d.get("kind") == "monthly"),
                     key=lambda d: d["period_end"], reverse=True)
    index = {
        "format": FORMAT_VERSION,
        "updated": _now(),
        "days": [{"date": d["date"], "count": len(d["papers"]),
                  "fields": sorted({p["field"] for p in d["papers"]}),
                  "top_headlines": [p["headline"] for p in d["papers"][:3]]} for d in days],
        "weekly": [_review_entry(d) for d in weekly],
        "monthly": [_review_entry(d) for d in monthly],
    }
    _dump(data / "index.json", index)
    _dump(data / "topics.json", {"format": FORMAT_VERSION, "groups": taxonomy_json()})
    if days:
        shutil.copyfile(data / f"{days[0]['date']}.json", data / "latest.json")

    def item(d):
        ident = d.get("id") or d["date"]
        label = headings(d)[0] if d.get("kind", "daily") != "daily" else long_date(date.fromisoformat(d["date"]))
        return {"id": ident, "label": label, "count": len(d["papers"]),
                "headlines": [p["headline"] for p in d["papers"][:3]]}

    page = _env().get_template("index.html.j2").render(
        **site_context(root="", active="home"),
        days=[item(d) for d in days],
        sections=[("Monthly reviews", [item(d) for d in monthly]),
                  ("Weekly reviews", [item(d) for d in weekly]),
                  ("Earlier daily digests", [item(d) for d in days[1:]])],
    )
    (site / "index.html").write_text(page, encoding="utf-8")
    for name in ("idea", "search", "saved"):
        (site / f"{name}.html").write_text(
            _env().get_template(f"{name}.html.j2").render(**site_context(root="", active=name)), encoding="utf-8")
    _dump(data / "search.json", {"format": FORMAT_VERSION, "papers": search_index(days)})
    for f in STATIC.iterdir():      # app icon + manifest so the site can be added to a home screen
        shutil.copyfile(f, site / f.name)
    (site / "privacy.html").write_text(PRIVACY_HTML, encoding="utf-8")
    (site / ".nojekyll").write_text("")
