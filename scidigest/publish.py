"""Publish reports as a small static site + JSON feed that the iPhone app reads.

Layout written under the site folder (served by GitHub Pages):
  index.html                    list of all reports (for browsers)
  reports/YYYY-MM-DD.html       the full HTML report for each day
  data/index.json               list of days, newest first
  data/latest.json              copy of the newest day
  data/YYYY-MM-DD.json          one day's digest

JSON format version 1. The iPhone app's Models.swift mirrors these field names.
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import date, datetime, timezone
from pathlib import Path

from markupsafe import escape

FORMAT_VERSION = 1


def _plain(citation: str) -> str:
    return re.sub(r"\*(.+?)\*", r"\1", citation)


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
    }


def day_json(entries, day: date, scanned: int, journals: list[str], ai: bool) -> dict:
    return {
        "format": FORMAT_VERSION,
        "date": day.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scanned": scanned,
        "journals": journals,
        "ai_summaries": ai,
        "papers": [paper_json(e) for e in entries],
    }


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


def publish(site: Path, digest: dict, html_report: Path) -> Path:
    data = site / "data"
    reports = site / "reports"
    data.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    day = digest["date"]

    def dump(path: Path, obj) -> None:
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")

    dump(data / f"{day}.json", digest)
    shutil.copyfile(html_report, reports / f"{day}.html")

    # Fill in any day whose HTML page is missing (e.g. lost or never committed).
    from .report import html_from_json
    for f in data.glob("????-??-??.json"):
        page = reports / f"{f.stem}.html"
        if not page.exists():
            page.write_text(html_from_json(json.loads(f.read_text(encoding="utf-8"))), encoding="utf-8")

    # Rebuild the index from every day file on disk (so reruns are idempotent).
    days = []
    for f in sorted(data.glob("????-??-??.json"), reverse=True):
        d = json.loads(f.read_text(encoding="utf-8"))
        days.append({
            "date": d["date"],
            "count": len(d["papers"]),
            "fields": sorted({p["field"] for p in d["papers"]}),
            "top_headlines": [p["headline"] for p in d["papers"][:3]],
        })
    dump(data / "index.json", {"format": FORMAT_VERSION, "updated": digest["generated_at"], "days": days})
    shutil.copyfile(data / f"{days[0]['date']}.json", data / "latest.json")

    rows = "\n".join(
        f'<li><a href="reports/{d["date"]}.html">{d["date"]}</a> · {d["count"]} papers'
        f'<br><small>{escape(" · ".join(d["top_headlines"]))}</small></li>'
        for d in days)
    (site / "index.html").write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Science Digest</title>
<style>:root{{--bg:#fbfaf7;--ink:#1d1d1f;--muted:#5f6368;--accent:#2f5d8a}}
@media (prefers-color-scheme:dark){{:root{{--bg:#141517;--ink:#ececec;--muted:#a3a7ad;--accent:#8db6e0}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:17px/1.6 Georgia,serif}}
main{{max-width:760px;margin:0 auto;padding:40px 16px}}a{{color:var(--accent)}}small{{color:var(--muted)}}
li{{margin-bottom:14px}}</style></head><body><main><h1>Daily Science Digest</h1>
<p><small>New research from leading journals, explained for science students.</small></p>
<ol reversed>{rows}</ol></main></body></html>""", encoding="utf-8")
    (site / "privacy.html").write_text(PRIVACY_HTML, encoding="utf-8")
    (site / ".nojekyll").write_text("")
    return data / f"{day}.json"
