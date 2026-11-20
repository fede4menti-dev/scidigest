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

from .report import headings, html_from_json, long_date

FORMAT_VERSION = 1
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
main{max-width:700px;margin:0 auto;padding:40px 16px}</style></head><body><main>
<h1>SciDigest Privacy Policy</h1>
<p><strong>SciDigest does not collect, store or share any personal data.</strong></p>
<ul>
<li>No account, sign-in, analytics, advertising or tracking.</li>
<li>The app downloads the daily report files from this website (hosted on GitHub Pages). Like any website,
GitHub may keep standard server logs such as IP addresses; see GitHub's privacy statement.</li>
<li>Your settings (report address, reminder time) and downloaded reports are stored only on your device.</li>
<li>Daily reminders are local notifications scheduled on your device. No push server is used.</li>
<li>Links to papers open in your browser and are subject to those websites' own policies.</li>
</ul>
<p>Summaries in SciDigest are written by an AI model from publicly available abstracts and open-access papers,
and may contain mistakes. Always check the original paper.</p>
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


def rebuild_site(site: Path) -> None:
    data, reports = site / "data", site / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    digests = {}
    for f in data.glob("*.json"):
        if f.stem in ("index", "latest"):
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
    if days:
        shutil.copyfile(data / f"{days[0]['date']}.json", data / "latest.json")

    def rows(items, ident):
        return "\n".join(
            f'<li><a href="reports/{ident(d)}.html">{escape(headings(d)[0] if d.get("kind","daily") != "daily" else long_date(date.fromisoformat(d["date"])))}</a>'
            f' · {len(d["papers"])} papers<br><small>{escape(" · ".join(p["headline"] for p in d["papers"][:3]))}</small></li>'
            for d in items)

    sections = ""
    if monthly:
        sections += f"<h2>Monthly reviews</h2><ul>{rows(monthly, lambda d: d['id'])}</ul>"
    if weekly:
        sections += f"<h2>Weekly reviews</h2><ul>{rows(weekly, lambda d: d['id'])}</ul>"
    sections += f"<h2>Daily digests</h2><ul>{rows(days, lambda d: d.get('id') or d['date'])}</ul>"
    (site / "index.html").write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Science Digest</title>
<style>:root{{--bg:#fbfaf7;--ink:#1d1d1f;--muted:#5f6368;--accent:#2f5d8a}}
@media (prefers-color-scheme:dark){{:root{{--bg:#141517;--ink:#ececec;--muted:#a3a7ad;--accent:#8db6e0}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:17px/1.6 Georgia,serif}}
main{{max-width:760px;margin:0 auto;padding:40px 16px}}a{{color:var(--accent)}}small{{color:var(--muted)}}
h2{{font-size:1.2rem;margin-top:32px}}ul{{padding-left:20px}}li{{margin-bottom:14px}}</style></head><body><main>
<h1>Science Digest</h1>
<p><small>New research from leading journals, explained for science students. Daily picks, a weekly review every Sunday and a monthly review on the 1st.</small></p>
{sections}</main></body></html>""", encoding="utf-8")
    (site / "privacy.html").write_text(PRIVACY_HTML, encoding="utf-8")
    (site / ".nojekyll").write_text("")
