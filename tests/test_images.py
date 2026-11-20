"""Image selection: only reusable licences, clear labels, credit always present."""
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


def page(i, lic, mime="image/jpeg", width=900, artist="Jane Doe <a href='x'>site</a> jane@example.com"):
    return {"index": i, "imageinfo": [{
        "mime": mime, "width": width, "thumburl": f"https://upload.wikimedia.org/thumb/{i}.jpg?utm=x",
        "descriptionurl": f"https://commons.wikimedia.org/wiki/File:{i}.jpg",
        "extmetadata": {"LicenseShortName": {"value": lic}, "Artist": {"value": artist},
                        "ImageDescription": {"value": "<b>A mosquito</b> on skin"},
                        "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0"}}}]}


def test_wikimedia_skips_restricted_licences_and_cleans_credit(monkeypatch):
    pages = {"a": page(1, "CC BY-NC 4.0"), "b": page(2, "CC BY-SA 4.0", mime="application/ogg"),
             "c": page(3, "CC BY-SA 4.0", width=300), "d": page(4, "CC BY-SA 4.0")}
    monkeypatch.setattr(images.requests, "get", lambda *a, **k: Resp({"query": {"pages": pages}}))
    img = images.wikimedia_image("malaria mosquito")
    assert img["url"] == "https://upload.wikimedia.org/thumb/4.jpg"
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
    monkeypatch.setattr("scidigest.__main__.wikimedia_image", lambda q: {"kind": "illustration", "q": q})
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
