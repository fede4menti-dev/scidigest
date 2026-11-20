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
    if "selections" in schema_keys:
        return _fake_response({"selections": [
            {"index": 1, "topic": "astronomy", "editors_pick": True, "score": 8, "field": "Astronomy", "reason": "early galaxy"},
            {"index": 0, "topic": "cell_molecular", "editors_pick": False, "score": 7, "field": "Biochemistry",
             "reason": "plastic recycling"}]})
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
    assert 'id="p1" data-topic="astronomy"' in html and 'id="p2" data-topic="cell_molecular"' in html
    assert html.index('id="p1"') < html.index("More by topic") < html.index('id="p2"')
    assert "More by topic" in html and "Cellular &amp; Molecular" in html
    assert "&lt;b&gt;safe&lt;/b&gt;" in html                            # escaped
    assert "<em>Nature</em>" in html and 'id="ref2"' in html            # references
    assert any("FULLTEXT_MARKER" in p for p in PROMPTS)
    assert html.count('class="pill full"') == 1                          # only the paper with full text
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
                      "published", "doi", "url", "citation", "free_copy", "featured_on", "image",
                      "category", "category_name", "editors_pick", "preprint"}
    assert "*" not in p["citation"] and isinstance(p["significance"], int)
    assert (site / "reports" / f"{day['date']}.html").exists() and (site / "index.html").exists()
    assert "collects as little as possible" in (site / "privacy.html").read_text()
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


def test_topic_picks_and_quota(monkeypatch):
    """Editor's picks first (max `top`), then at most per_topic picks per topic, invalid topics dropped."""
    from scidigest.fetch import Article
    arts = [Article(id=str(i), title=f"T{i}", journal="J", link="", abstract="a" * 400, published=None)
            for i in range(8)]
    sel = [
        {"index": 0, "topic": "physics", "editors_pick": True, "score": 9, "field": "f", "reason": ""},
        {"index": 1, "topic": "physics", "editors_pick": True, "score": 8, "field": "f", "reason": ""},   # over top=1
        {"index": 2, "topic": "physics", "editors_pick": False, "score": 7, "field": "f", "reason": ""},
        {"index": 3, "topic": "physics", "editors_pick": False, "score": 6, "field": "f", "reason": ""},   # over quota
        {"index": 4, "topic": "climate", "editors_pick": False, "score": 5, "field": "f", "reason": ""},
        {"index": 4, "topic": "climate", "editors_pick": False, "score": 5, "field": "f", "reason": ""},   # duplicate
        {"index": 9, "topic": "climate", "editors_pick": False, "score": 5, "field": "f", "reason": ""},   # bad index
    ]
    monkeypatch.setattr(ai, "_ask_json", lambda *a, **k: {"selections": sel})
    picks = ai.rank(arts, top=1, per_topic=2)
    assert [a.id for a, _ in picks] == ["0", "1", "2", "4"]
    assert [p["editors_pick"] for _, p in picks] == [True, False, False, False]


def test_arxiv_preprint_flag_and_card_page(tmp_path):
    from scidigest.publish import paper_json
    from scidigest.report import excerpt
    long = "First sentence is here. " + "word " * 80
    assert excerpt(long).endswith("…") and len(excerpt(long)) < 240            # very short first sentence: cut at a word
    two = "This opening sentence is long enough to be a good card intro on its own here. " + "more " * 60
    assert excerpt(two).endswith("here.")
    assert excerpt("short") == "short"
    site = _run(tmp_path, "2026-11-18")
    html = (site / "reports" / "2026-11-18.html").read_text()
    assert 'class="card"' in html and "<summary>" in html and "Read more" in html
    assert "References" in html and 'id="ref1"' in html
    topics = json.loads((site / "data" / "topics.json").read_text())
    assert len(topics["groups"]) == 6 and sum(len(g["topics"]) for g in topics["groups"]) == 18


def test_site_settings_panel_and_home_screen_files(tmp_path):
    site = _run(tmp_path, "2026-11-18")
    for page in (site / "index.html", site / "reports" / "2026-11-18.html"):
        html = page.read_text()
        assert 'id="settings"' in html and "Save and refresh papers" in html and "data-open-settings" in html
        assert html.count('name="topic"') == 18 and "Mathematics &amp; Statistics" in html
        assert 'rel="manifest"' in html and "apple-touch-icon" in html
    assert '<main data-report>' in (site / "reports" / "2026-11-18.html").read_text()
    assert 'href="../index.html"' in (site / "reports" / "2026-11-18.html").read_text()
    for f in ("manifest.webmanifest", "apple-touch-icon.png", "icon-192.png", "icon-512.png"):
        assert (site / f).exists()
    assert json.loads((site / "manifest.webmanifest").read_text())["display"] == "standalone"


def test_backfill_tags_old_papers(tmp_path):
    from scidigest.backfill import backfill_topics, guess_topic
    assert guess_topic("Astronomy", "A star spirals") == "astronomy"
    assert guess_topic("Materials Science / Energy", "perovskite solar cells") == "materials"
    assert guess_topic("Ecology / Conservation", "Farming reshuffles species") == "ecology"
    site = _run(tmp_path, "2026-11-18", "--no-reviews")
    f = site / "data" / "2026-11-18.json"
    d = json.loads(f.read_text())
    for p in d["papers"]:
        p.pop("category"); p.pop("category_name"); p.pop("editors_pick")
        p["field"] = "Astronomy"
    f.write_text(json.dumps(d))
    assert backfill_topics(site, use_ai=False, log=lambda *_: None) == len(d["papers"])
    d = json.loads(f.read_text())
    assert all(p["category"] == "astronomy" and p["category_name"] == "Astronomy & Planetary Science" for p in d["papers"])
    assert backfill_topics(site, use_ai=False) == 0          # nothing left to do


def test_untagged_papers_do_not_match_a_topic_filter(tmp_path):
    site = _run(tmp_path, "2026-11-18")
    html = (site / "reports" / "2026-11-18.html").read_text()
    assert "!c.dataset.topic||" not in html


def test_idea_page_and_navigation(tmp_path, monkeypatch):
    monkeypatch.setenv("SCIDIGEST_IDEA_URL", "https://checker.example.dev")
    site = _run(tmp_path, "2026-11-18")
    idea = (site / "idea.html").read_text()
    assert "Idea Check" in idea and 'id="question"' in idea and '"https://checker.example.dev"' in idea
    assert 'href="idea.html" aria-current="page"' in idea                        # active tab
    home = (site / "index.html").read_text()
    assert 'href="index.html" aria-current="page"' in home and 'href="idea.html"' in home
    rep = (site / "reports" / "2026-11-18.html").read_text()
    assert 'class="back" href="../index.html"' in rep and 'href="../idea.html"' in rep
    assert 'class="tabbar"' in rep and 'id="idea-url"' in rep                      # tab bar + idea settings


def test_spending_cap_keeps_editors_picks_and_drops_topic_picks(tmp_path, monkeypatch):
    calls = []
    def create(**kw):
        calls.append(1)
        r = fake_create(**kw)
        r.usage = SimpleNamespace(input_tokens=200_000, output_tokens=20_000)   # ~$1.20 per call
        return r
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("SCIDIGEST_MAX_RUN_USD", "1.0")
    monkeypatch.setattr(ai, "_usage", {"input": 0, "output": 0, "calls": 0})
    fake = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    site = tmp_path / "site"
    with mock.patch.object(ai, "client", return_value=fake):
        main(["--feed-file", "Nature", str(FIX), "--no-crossref", "--no-fulltext", "--no-images",
              "--out", str(tmp_path / "r"), "--site", str(site), "--today", "2026-11-18", "--no-reviews"])
    assert len(calls) == 1, "only the ranking call ran; the cap stopped the summaries"
    d = json.loads((site / "data" / "2026-11-18.json").read_text())
    assert [p["editors_pick"] for p in d["papers"]] == [True]          # topic pick dropped
    assert d["papers"][0]["based_on"] == "abstract"                     # editor's pick kept, abstract quoted
    assert "about $1.20" in ai.usage_line()


def test_second_run_same_day_is_skipped_unless_forced(tmp_path, capsys):
    site = _run(tmp_path, "2026-11-18")
    capsys.readouterr()
    (site / "idea.html").unlink()
    main(["--no-ai", "--site", str(site), "--out", str(tmp_path / "r"), "--today", "2026-11-18"])
    assert "already exists; skipping" in capsys.readouterr().out
    assert (site / "idea.html").exists(), "pages are still rebuilt (free) on a skipped run"


def test_search_saved_pages_and_offline_files(tmp_path):
    site = _run(tmp_path, "2026-11-18")
    idx = json.loads((site / "data" / "search.json").read_text())
    assert len(idx["papers"]) == 2 and idx["papers"][0]["r"].startswith("reports/2026-11-18.html#p")
    for page in ("search.html", "saved.html", "idea.html", "index.html"):
        html = (site / page).read_text()
        assert 'href="search.html"' in html and 'href="saved.html"' in html and 'src="app.js"' in html
        assert 'id="account-box"' in html and 'id="export-data"' in html and 'name="size"' in html
    for f in ("app.js", "sw.js"):
        assert (site / f).exists()
    rep = (site / "reports" / "2026-11-18.html").read_text()
    assert 'data-act="save"' in rep and 'data-act="cite"' in rep and 'data-report="reports/2026-11-18.html#p1"' in rep
    assert 'src="../app.js"' in rep
