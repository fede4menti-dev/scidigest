"""Offline tests: no network, Claude calls mocked."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from scidigest import ai
from scidigest.__main__ import main
from scidigest.citations import apa
from scidigest.fetch import parse_feed

FIX = Path(__file__).parent / "fixtures" / "sample_nature.rss"


def articles():
    return parse_feed(FIX.read_bytes(), {"journal": "Nature", "weight": 1.0})


def test_parse_filters_corrections_and_extracts_fields():
    arts = articles()
    assert [a.doi for a in arts] == ["10.9999/test.0001", "10.9999/test.0002"]
    a = arts[0]
    assert a.authors == ["Ada Lovelace", "Alan M. Turing"]
    assert "&" in a.title and "<p>" not in a.abstract
    assert a.volume == "700" and a.year == 2026


def test_apa_citation():
    c = apa(articles()[0])
    assert c.startswith("Lovelace, A., & Turing, A. M. (2026).")
    assert "*Nature*, *700*, 12." in c and c.endswith("https://doi.org/10.9999/test.0001")


def test_copied_fraction():
    src = "the quick brown fox jumps over the lazy dog near the river bank today"
    assert ai.copied_fraction(src, src) == 1.0
    assert ai.copied_fraction("A totally different sentence written in other words entirely here.", src) == 0.0


def _fake_response(payload):
    return SimpleNamespace(stop_reason="end_turn",
                           content=[SimpleNamespace(type="text", text=json.dumps(payload))])


def fake_create(**kw):
    PROMPTS.append(kw["messages"][0]["content"])
    schema_keys = kw["output_config"]["format"]["schema"]["properties"].keys()
    assert kw["model"] == "claude-opus-5-5" and kw["fallbacks"] == "default"
    if "picks" in schema_keys:
        return _fake_response({"picks": [
            {"index": 1, "score": 8, "field": "Astronomy", "reason": "early galaxy"},
            {"index": 0, "score": 7, "field": "Biochemistry", "reason": "plastic recycling"}]})
    return _fake_response({
        "headline": "Plain headline <b>safe</b>",
        "summary": "Para one in my own words.\nPara two in my own words.",
        "why_it_matters": "Because reasons.",
        "key_terms": [{"term": "Enzyme", "meaning": "a protein that speeds up a reaction"}],
        "limitations": "Lab only."})


PROMPTS = []


def test_end_to_end_with_mocked_claude(tmp_path, monkeypatch):
    from scidigest import __main__ as cli
    from scidigest.fulltext import FreeCopy
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(cli, "find_free_copy", lambda a, email: FreeCopy(
        url="https://europepmc.org/article/PMC/PMC1", version="Published version", host="Europe PMC",
        license="cc by", text="FULLTEXT_MARKER methods and results") if a.doi.endswith("0001") else None)
    fake = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=fake_create)))
    with mock.patch.object(ai, "client", return_value=fake):
        main(["--feed-file", "Nature", str(FIX), "--no-crossref", "--out", str(tmp_path)])
    html = next(tmp_path.glob("*.html")).read_text()
    md = next(tmp_path.glob("*.md")).read_text()
    assert html.index("Astronomy") < html.index("Biochemistry")       # ranking order kept
    assert "&lt;b&gt;safe&lt;/b&gt;" in html                            # escaped
    assert "<em>Nature</em>" in html and 'id="ref2"' in html            # references
    assert any("FULLTEXT_MARKER" in p for p in PROMPTS)
    assert "Summarised from full text" in html and "Summarised from abstract" in html
    assert "https://europepmc.org/article/PMC/PMC1" in html and "Free to read" in md
    assert "## References" in md and "https://doi.org/10.9999/test.0001" in md


def test_no_ai_mode(tmp_path):
    main(["--no-ai", "--no-fulltext", "--feed-file", "Nature", str(FIX), "--no-crossref", "--out", str(tmp_path), "--top", "5"])
    md = next(tmp_path.glob("*.md")).read_text()
    assert "quoted, not paraphrased" in md and md.count("doi.org/10.9999") >= 2


def test_site_publish_json_contract(tmp_path):
    """Locks the JSON fields the iPhone app (Models.swift) decodes."""
    site = tmp_path / "site"
    main(["--no-ai", "--no-fulltext", "--no-crossref", "--feed-file", "Nature", str(FIX),
          "--out", str(tmp_path / "r"), "--site", str(site)])
    idx = json.loads((site / "data" / "index.json").read_text())
    assert idx["format"] == 1 and len(idx["days"]) == 1
    day = idx["days"][0]
    assert set(day) == {"date", "count", "fields", "top_headlines"}
    assert idx["weekly"] == [] and idx["monthly"] == []
    d = json.loads((site / "data" / f"{day['date']}.json").read_text())
    assert d == json.loads((site / "data" / "latest.json").read_text())
    assert set(d) == {"format", "kind", "id", "title", "date", "period_start", "period_end", "generated_at",
                      "scanned", "journals", "ai_summaries", "intro", "papers"}
    assert d["kind"] == "daily" and d["id"] == d["date"]
    p = d["papers"][0]
    assert set(p) == {"rank", "headline", "original_title", "journal", "field", "significance", "reason",
                      "summary", "why_it_matters", "limitations", "key_terms", "based_on", "authors",
                      "published", "doi", "url", "citation", "free_copy", "featured_on", "image"}
    assert "*" not in p["citation"] and isinstance(p["significance"], int)
    assert (site / "reports" / f"{day['date']}.html").exists() and (site / "index.html").exists()
    assert "does not collect" in (site / "privacy.html").read_text()
    # rerun same day: still one entry (idempotent)
    main(["--no-ai", "--no-fulltext", "--no-crossref", "--feed-file", "Nature", str(FIX),
          "--out", str(tmp_path / "r"), "--site", str(site)])
    assert len(json.loads((site / "data" / "index.json").read_text())["days"]) == 1


def test_one_failed_summary_does_not_break_report(monkeypatch):
    arts = articles()
    def boom(*a, **k):
        raise RuntimeError("model declined this request")
    monkeypatch.setattr(ai, "summarize", boom)
    out = ai.summarize_many([(arts[0], "", "")])
    assert out[0]["headline"] == arts[0].title and "not paraphrased" in out[0]["based_on"]


def test_nejm_letters_and_editorials_filtered():
    from scidigest.fetch import is_research
    assert is_research("Trial of X", "10.1056/NEJMoa2512345")
    assert is_research("Review of Y", "10.1056/NEJMra2400001")
    assert not is_research("Meningococcal B Vaccine to Prevent Gonorrhea", "10.1056/NEJMc2611609")
    assert not is_research("Some editorial", "10.1056/NEJMe2600001")
    assert not is_research("Some perspective", "10.1056/NEJMp2600001")
    assert is_research("Nature paper", "10.1038/s41586-026-01234-5")


def test_short_abstract_papers_skipped_before_ranking(tmp_path):
    from scidigest.fetch import Article
    long = "x " * 200
    arts = [Article(id=str(i), title=f"T{i}", journal="Nature", link="", abstract=(long if i < 3 else "cite only"),
                    published=None, doi=None, prior=1.0) for i in range(5)]
    from scidigest import __main__ as cli
    seen = {}
    def fake_rank(cands, top, **kw):
        seen["n"] = len(cands)
        return [(a, {"score": 5, "field": "X", "reason": ""}) for a in cands[:top]]
    with mock.patch.object(cli, "fetch_all", return_value=arts), \
         mock.patch.object(cli.ai, "rank", fake_rank), \
         mock.patch.object(cli.ai, "summarize_many", lambda jobs, **k: [
             {"headline": "h", "summary": "s", "why_it_matters": "w", "key_terms": [], "limitations": "", "based_on": "abstract"}
             for _ in jobs]), \
         mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "x"}):
        cli.main(["--top", "2", "--no-crossref", "--no-fulltext", "--out", str(tmp_path)])
    assert seen["n"] == 3


def test_missing_report_pages_are_rebuilt_from_json(tmp_path):
    site = tmp_path / "site"
    args = ["--no-ai", "--no-fulltext", "--no-crossref", "--feed-file", "Nature", str(FIX),
            "--out", str(tmp_path / "r"), "--site", str(site)]
    main(args)
    page = next((site / "reports").glob("*.html"))
    old = (site / "data" / f"{page.stem}.json").read_text()
    (site / "data" / "2020-01-01.json").write_text(old.replace(page.stem, "2020-01-01"))
    page.unlink()
    main(args)
    assert page.exists()
    rebuilt = (site / "reports" / "2020-01-01.html").read_text()
    assert "Daily Science Digest" in rebuilt and "doi.org/10.9999/test.0001" in rebuilt


def test_gitignore_does_not_hide_site_reports():
    rules = (Path(__file__).parents[1] / ".gitignore").read_text().split()
    assert "reports/" not in rules and "/reports/" in rules


def test_lancet_tags():
    from scidigest.fetch import is_research, strip_tag
    assert is_research("[Articles] Seasonal mass vaccination with R21")
    assert not is_research("[Comment] Malaria vaccines at scale")
    assert not is_research("[Correspondence] A reply")
    assert strip_tag("[Articles] Seasonal mass vaccination") == "Seasonal mass vaccination"


def _run(tmp_path, today, *extra):
    site = tmp_path / "site"
    main(["--no-ai", "--no-fulltext", "--no-crossref", "--feed-file", "Nature", str(FIX),
          "--out", str(tmp_path / "r"), "--site", str(site), "--today", today, *extra])
    return site


def _day(site, d):
    return json.loads((site / "data" / f"{d}.json").read_text())


def test_repeat_rules(tmp_path):
    site = _run(tmp_path, "2026-11-16")
    assert len(_day(site, "2026-11-16")["papers"]) == 2
    _run(tmp_path, "2026-11-16")                                  # same-day rerun: same picks, no "repeat"
    assert all(p["featured_on"] == [] for p in _day(site, "2026-11-16")["papers"])
    _run(tmp_path, "2026-11-17")                                  # next day: blocked, no empty digest written
    assert not (site / "data" / "2026-11-17.json").exists()
    _run(tmp_path, "2026-11-19")                                  # 3 days later: allowed once more
    d = _day(site, "2026-11-19")
    assert d["papers"] and all(p["featured_on"] == ["2026-11-16"] for p in d["papers"])
    _run(tmp_path, "2026-11-25")                                  # already shown twice: never again
    assert not (site / "data" / "2026-11-25.json").exists()


def test_weekly_and_monthly_reviews(tmp_path):
    site = _run(tmp_path, "2026-11-16")
    _run(tmp_path, "2026-11-22")                                  # Sunday -> weekly review Nov 16-22
    idx = json.loads((site / "data" / "index.json").read_text())
    w = json.loads((site / "data" / "weekly-2026-11-22.json").read_text())
    assert idx["weekly"][0]["id"] == "weekly-2026-11-22" and w["kind"] == "weekly"
    assert (w["period_start"], w["period_end"]) == ("2026-11-16", "2026-11-22")
    assert w["title"] == "Weekly Review: Nov 16 to Nov 22, 2026"
    assert len(w["papers"]) == 2 and all(p["featured_on"] == ["2026-11-16", "2026-11-22"] for p in w["papers"])
    assert "From the daily digest of" in (site / "reports" / "weekly-2026-11-22.html").read_text()
    assert not idx["monthly"]
    _run(tmp_path, "2026-12-01", "--no-reviews")                  # --no-reviews: no monthly
    assert not list((site / "data").glob("monthly-*"))
    site = _run(tmp_path, "2026-12-01", "--review", "monthly")    # monthly review of November
    m = json.loads((site / "data" / "monthly-2026-11.json").read_text())
    assert m["title"] == "Monthly Review: November 2026" and m["period_end"] == "2026-11-30"
    assert "Monthly reviews" in (site / "index.html").read_text()
    # latest.json stays the newest *daily* digest
    assert json.loads((site / "data" / "latest.json").read_text())["kind"] == "daily"


def test_due_reviews():
    from datetime import date
    from scidigest.reviews import due_reviews, monthly_period
    assert due_reviews(date(2026, 11, 22)) == ["weekly"]            # Sunday
    assert due_reviews(date(2026, 11, 23)) == []
    assert due_reviews(date(2026, 12, 1)) == ["monthly"]
    assert due_reviews(date(2027, 8, 1)) == ["weekly", "monthly"]   # a Sunday the 1st
    assert monthly_period(date(2027, 1, 1)) == (date(2026, 12, 1), date(2026, 12, 31))


def test_paper_dates_shown(tmp_path):
    site = _run(tmp_path, "2026-11-18")
    html = (site / "reports" / "2026-11-18.html").read_text()
    assert "Published Nov 18, 2026" in html and "Published Nov 17, 2026" in html
    assert "Wednesday, November 18, 2026" in html
