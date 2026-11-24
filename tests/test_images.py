"""Image selection: only reusable licences, clear labels, credit always present."""
import json
from types import SimpleNamespace

from scidigest import images
from scidigest.__main__ import pick_image
from scidigest.fulltext import FreeCopy


class Resp:
    def __init__(self, js, status=200):
        self._js, self.status_code, self.headers = js, status, {}

    def json(self):
        return self._js

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def page(i, lic, mime="image/jpeg", width=900, artist="Jane Doe <a href='x'>site</a> jane@example.com",
         title="File:Malaria mosquito on skin.jpg", cats="Anopheles|Mosquitoes", desc="<b>A mosquito</b> on skin"):
    return {"index": i, "title": title, "imageinfo": [{
        "mime": mime, "width": width, "url": f"https://upload.wikimedia.org/wikipedia/commons/a/ab/Pic{i}.jpg",
        "descriptionurl": f"https://commons.wikimedia.org/wiki/File:{i}.jpg",
        "extmetadata": {"LicenseShortName": {"value": lic}, "Artist": {"value": artist},
                        "ImageDescription": {"value": desc}, "Categories": {"value": cats},
                        "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0"}}}]}


def test_wikimedia_skips_restricted_licences_and_cleans_credit(monkeypatch):
    pages = {"a": page(1, "CC BY-NC 4.0"), "b": page(2, "CC BY-SA 4.0", mime="application/ogg"),
             "c": page(3, "CC BY-SA 4.0", width=300), "d": page(4, "CC BY-SA 4.0")}
    monkeypatch.setattr(images.requests, "get", lambda *a, **k: Resp({"query": {"pages": pages}}))
    img = images.wikimedia_image("malaria mosquito")
    # always a standard-size thumbnail, never the rate-limited full-size original
    assert img["url"] == "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Pic4.jpg/500px-Pic4.jpg"
    assert img["kind"] == "illustration" and img["license"] == "CC BY-SA 4.0"
    assert img["credit"] == "Jane Doe site, via Wikimedia Commons"          # no HTML, no email
    assert img["caption"] == "A mosquito on skin"


def test_wikimedia_failure_is_soft(monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("offline")
    monkeypatch.setattr(images.requests, "get", boom)
    assert images.wikimedia_image("x", log=lambda *_: None) is None
    assert images.wikimedia_image("") is None


def test_pick_image_prefers_open_access_figure(monkeypatch):
    monkeypatch.setattr("scidigest.__main__.wikimedia_image", lambda q, fallback="": {"kind": "illustration", "q": q})
    art = SimpleNamespace(journal="PLOS Biology")
    copy = FreeCopy(url="https://europepmc.org/article/PMC/PMC1", version="Published version", host="Europe PMC",
                    license="cc by", figures=[{"label": "Fig 1", "caption": "orig", "url": "https://e/f1.jpg"},
                                              {"label": "Fig 2", "caption": "orig2", "url": "https://e/f2.jpg"}])
    img = pick_image(art, {"figure_index": 1, "figure_caption": "Plain words.", "image_query": "q"}, copy)
    assert img["kind"] == "figure" and img["url"] == "https://e/f2.jpg" and img["caption"] == "Plain words."
    assert img["credit"] == "Fig 2 from the paper, PLOS Biology" and img["license"] == "CC BY"
    assert img["license_url"] == "https://creativecommons.org/licenses/by/4.0/"
    # no usable figure -> illustrative photo from the suggested query
    assert pick_image(art, {"figure_index": -1, "image_query": "mosquito"}, copy) == {"kind": "illustration", "q": "mosquito"}
    assert pick_image(art, {"figure_index": 5, "image_query": "m"}, None)["q"] == "m"


def test_non_reusable_open_access_gives_no_figures():
    from scidigest import fulltext
    assert not images.reusable("cc by-nc-nd") and images.reusable("cc by")


def test_thumbnail_urls_and_query_fallbacks(monkeypatch):
    assert images.thumb_url("https://upload.wikimedia.org/wikipedia/commons/9/91/A_b.jpg", 3000) == \
        "https://upload.wikimedia.org/wikipedia/commons/thumb/9/91/A_b.jpg/960px-A_b.jpg"
    assert images.thumb_url("https://upload.wikimedia.org/wikipedia/commons/9/91/A_b.jpg", 700).endswith("/500px-A_b.jpg")
    assert images.thumb_url("https://europepmc.org/articles/PMC1/bin/f1.jpg", None) == "https://europepmc.org/articles/PMC1/bin/f1.jpg"
    asked = []
    def fake_get(url, params=None, **k):
        asked.append(params["gsrsearch"])
        pages = ({"x": page(1, "CC BY 4.0", title="File:Neuroscience lab microscope.jpg", cats="Neuroscience|Microscopes")}
                 if params["gsrsearch"].startswith("Neuroscience") else {})
        return Resp({"query": {"pages": pages}})
    monkeypatch.setattr(images.requests, "get", fake_get)
    img = images.wikimedia_image("hypothalamic orexin neurons firing", fallback="Neuroscience")
    assert img and asked == ["hypothalamic orexin neurons firing filetype:bitmap", "hypothalamic orexin filetype:bitmap",
                             "Neuroscience filetype:bitmap"]


def test_backfill_images_fixes_originals_and_fills_missing(tmp_path, monkeypatch):
    from scidigest import backfill
    site = tmp_path / "site"; (site / "data").mkdir(parents=True)
    d = {"date": "2026-11-21", "papers": [
        {"field": "Biology", "image_query": "ant head", "image": {"kind": "illustration",
         "url": "https://upload.wikimedia.org/wikipedia/commons/e/ea/Ant.jpg"}},
        {"field": "Astronomy", "image_query": "radio telescope", "image": None}]}
    (site / "data" / "2026-11-21.json").write_text(json.dumps(d))
    monkeypatch.setattr(images, "wikimedia_image", lambda q, log=None, fallback="": {"kind": "illustration", "url": "https://x/" + q})
    assert backfill.backfill_images(site, pause=0, log=lambda *_: None, prewarm_newest=False) == 2
    out = json.loads((site / "data" / "2026-11-21.json").read_text())["papers"]
    assert out[0]["image"]["url"] == "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ea/Ant.jpg/500px-Ant.jpg"
    assert out[1]["image"]["url"] == "https://x/radio telescope"


def test_prewarm_retries_once_on_429(monkeypatch):
    calls = []
    class R:
        def __init__(self, c): self.status_code = c
        def close(self): pass
    seq = iter([429, 200, 404])
    monkeypatch.setattr(images.requests, "get", lambda u, **k: (calls.append(u), R(next(seq)))[1])
    monkeypatch.setattr(images.time, "sleep", lambda s: None)
    assert images.prewarm(["https://a", "https://b"], pause=0, log=lambda *_: None) == 1
    assert calls == ["https://a", "https://a", "https://b"]


def test_political_people_and_unrelated_photos_are_skipped(monkeypatch):
    pages = {
        "a": page(1, "CC0", title="File:Volodymyr Zelenskyy in May 2024 (cropped).jpg",
                  cats="Volodymyr Zelenskyy in May 2024|2022 Russo-Ukrainian War", desc="memories of the elderly"),
        "b": page(2, "CC BY 4.0", title="File:Elderly people at a memory clinic.jpg", cats="People with dementia|Portraits"),
        "c": page(3, "CC BY 4.0", title="File:Glacier in Bhutan.jpg", cats="Glaciers"),                 # unrelated
        "d": page(4, "CC BY-SA 4.0", title="File:Memory test card set.jpg", cats="Memory tests|Psychology equipment",
                  desc="A long description " * 20),
    }
    monkeypatch.setattr(images.requests, "get", lambda *a, **k: Resp({"query": {"pages": pages}}))
    img = images.wikimedia_image("elderly memory test")
    assert img["source_url"].endswith("File:4.jpg") and img["caption"] == "Memory test card set"   # its own name


def test_audit_removes_published_political_photo(tmp_path, monkeypatch):
    from scidigest import backfill
    site = tmp_path / "site"; (site / "data").mkdir(parents=True)
    bad = "https://commons.wikimedia.org/wiki/File:Volodymyr_Zelenskyy_in_May_2024.jpg"
    good = "https://commons.wikimedia.org/wiki/File:Radio_telescope.jpg"
    d = {"date": "2026-11-23", "papers": [
        {"headline": "Memory", "image_query": "elderly memory test", "image": {"kind": "illustration", "source_url": bad}},
        {"headline": "Pulsar", "image_query": "radio telescope", "image": {"kind": "illustration", "source_url": good}}]}
    (site / "data" / "2026-11-23.json").write_text(json.dumps(d))
    monkeypatch.setattr(images, "commons_metadata", lambda titles: {
        "File:Volodymyr Zelenskyy in May 2024.jpg": {"Categories": {"value": "Volodymyr Zelenskyy in May 2024"}},
        "File:Radio telescope.jpg": {"Categories": {"value": "Radio telescopes"}}})
    assert backfill.audit_images(site, log=lambda *_: None) == 1
    out = json.loads((site / "data" / "2026-11-23.json").read_text())["papers"]
    assert out[0]["image"] is None and out[1]["image"]["source_url"] == good


def test_people_photos_are_blocked_by_name_or_category():
    ok = {"Categories": {"value": "Stethoscopes|Medical equipment|Lists of tools"}}
    assert images.allowed_photo("File:Stethoscope on a desk.jpg", ok, "stethoscope")
    for title, cats in [("File:Elderly Miccosukee man (2986266479).jpg", "Native Americans"),
                        ("File:Doctor taking blood sample.png", "Blood tests"),
                        ("File:Blood sample tubes.jpg", "People in laboratories"),
                        ("File:Virology session 2008.jpg", "Virology|Laminar flow cabinets|Males in masks"),
                        ("File:Sampling lava with hammer and bucket.jpg", "Geologists from the United States|Pahoehoe lava")]:
        assert not images.allowed_photo(title, {"Categories": {"value": cats}}, "blood sample"), title
