"""Offline tests for the free full-text lookup (network calls faked)."""
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scidigest import fulltext
from scidigest.fetch import Article

FIX = Path(__file__).parent / "fixtures"
PAD = " Filler sentence to make the document long enough to count as real full text." * 30


def art(doi="10.9999/test.0001"):
    return Article(id=doi, title="T", journal="Nature", link="", abstract="short", published=None, doi=doi)


class Resp:
    def __init__(self, body=b"", js=None, ctype="application/json"):
        self.content, self._js, self.headers = body, js, {"Content-Type": ctype}
        self.raw = io.BytesIO(body)
        self.raw.read = (lambda n=-1, decode_content=True, _r=self.raw: io.BytesIO.read(_r, n))

    def json(self):
        return self._js

    def raise_for_status(self):
        pass


def make_pdf(text: str) -> bytes:
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 800
    for i in range(0, len(text), 90):
        c.drawString(40, y, text[i:i + 90])
        y -= 14
        if y < 40:
            c.showPage(); y = 800
    c.drawString(40, y - 20, "")
    c.save()
    return buf.getvalue()


def test_jats_to_text_keeps_science_and_skips_backmatter():
    t = fulltext.jats_to_text((FIX / "sample_jats.xml").read_bytes())
    for m in ("FICTIONAL TEST ABSTRACT", "INTRO_MARKER", "METHODS_MARKER", "RESULTS_MARKER",
              "repeated three times", "Breakdown rate"):
        assert m in t
    assert "SHOULD_BE_SKIPPED" not in t and "SHOULD_ALSO_BE_SKIPPED" not in t


def test_europe_pmc_route(monkeypatch):
    jats = (FIX / "sample_jats.xml").read_text().replace("INTRO_MARKER.", "INTRO_MARKER." + PAD)
    def fake_get(url, **kw):
        if url.endswith("/search"):
            return Resp(js={"resultList": {"result": [{"pmcid": "PMC123", "isOpenAccess": "Y",
                     "license": "cc by", "abstractText": "A much longer abstract from Europe PMC."}]}})
        if url.endswith("/PMC123/fullTextXML"):
            return Resp(body=jats.encode())
        raise AssertionError(f"unexpected call {url}")
    monkeypatch.setattr(fulltext.requests, "get", fake_get)
    a = art()
    copy = fulltext.find_free_copy(a, email=None)
    assert copy.host == "Europe PMC" and copy.url.endswith("PMC123") and "RESULTS_MARKER" in copy.text
    assert a.abstract.startswith("A much longer abstract")


def test_unpaywall_pdf_route(monkeypatch):
    pdf = make_pdf("PDF_BODY_MARKER preprint results." + PAD)
    calls = []
    def fake_get(url, **kw):
        calls.append((url, kw.get("params")))
        if url.endswith("/search"):
            return Resp(js={"resultList": {"result": []}})
        if "unpaywall" in url:
            return Resp(js={"is_oa": True, "best_oa_location": {
                "url_for_landing_page": "https://www.biorxiv.org/x", "url_for_pdf": "https://www.biorxiv.org/x.pdf",
                "host_type": "repository", "version": "submittedVersion", "license": "cc-by"}})
        if url.endswith(".pdf"):
            return Resp(body=pdf, ctype="application/pdf")
        raise AssertionError(url)
    monkeypatch.setattr(fulltext.requests, "get", fake_get)
    copy = fulltext.find_free_copy(art(), email="me@example.com")
    assert copy.version.startswith("Preprint") and "PDF_BODY_MARKER" in copy.text
    assert ("https://api.unpaywall.org/v2/10.9999/test.0001", {"email": "me@example.com"}) in calls


def test_no_email_skips_unpaywall_and_failures_are_soft(monkeypatch):
    def fake_get(url, **kw):
        assert "unpaywall" not in url
        raise ConnectionError("offline")
    monkeypatch.setattr(fulltext.requests, "get", fake_get)
    assert fulltext.find_free_copy(art(), email=None, log=lambda *_: None) is None
    assert fulltext.find_free_copy(art(doi=None), email="x@y.z") is None
