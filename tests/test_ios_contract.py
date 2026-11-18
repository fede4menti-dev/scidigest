"""Checks ios/SciDigest/Models.swift decodes exactly the JSON publish.py writes.

Swift uses .convertFromSnakeCase, so `why_it_matters` must appear as `whyItMatters`.
Optional Swift fields (Type?) must be the ones that can be null in JSON."""
import json
import re
from pathlib import Path

from scidigest.__main__ import main

ROOT = Path(__file__).parents[1]
FIX = Path(__file__).parent / "fixtures" / "sample_nature.rss"


def swift_struct_fields(name: str) -> dict[str, bool]:
    src = (ROOT / "ios" / "SciDigest" / "Models.swift").read_text()
    body = re.search(rf"struct {name}\b[^{{]*{{(.*?)\n}}", src, re.S).group(1)
    return {m.group(1): m.group(2) == "?" for m in re.finditer(r"^\s*let (\w+): [\w\[\]]+(\??)", body, re.M)}


def camel(snake: str) -> str:
    head, *rest = snake.split("_")
    return head + "".join(w.capitalize() for w in rest)


def check(obj: dict, struct: str, nullable: set[str] = frozenset()):
    fields = swift_struct_fields(struct)
    assert set(fields) == {camel(k) for k in obj}, struct
    for k in obj:
        assert fields[camel(k)] == (k in nullable), f"{struct}.{k} optionality"


def test_models_match_published_json(tmp_path):
    site = tmp_path / "site"
    main(["--no-ai", "--no-fulltext", "--no-crossref", "--feed-file", "Nature", str(FIX),
          "--out", str(tmp_path / "r"), "--site", str(site)])
    idx = json.loads((site / "data" / "index.json").read_text())
    day = json.loads((site / "data" / "latest.json").read_text())
    check(idx, "DigestIndex")
    check(idx["days"][0], "DayEntry")
    check(day, "Digest")
    check(day["papers"][0], "Paper", nullable={"published", "doi", "free_copy"})
    check({"term": "", "meaning": ""}, "KeyTerm")
    check({"url": "", "version": "", "host": "", "license": None}, "FreeCopy", nullable={"license"})
