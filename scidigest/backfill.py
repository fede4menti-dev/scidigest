"""Give a topic to published papers that don't have one (digests made before topics existed,
or a paper the ranker returned without a valid topic). Runs as part of each --site run."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .taxonomy import TOPIC_IDS, TOPICS, prompt_list, topic_name

# Keyword fallback for runs without AI. Checked in order; first match wins.
KEYWORDS = [
    ("astronomy", r"astro|cosmo|galax|planet|stellar|\bstars?\b|telescope|pulsar|black hole"),
    ("climate", r"climate|atmospher|carbon cycle|biogeochem|sustainab|environmental|ocean and atmos|emission"),
    ("earth_water", r"geolog|seism|earthquake|volcan|hydrolog|ocean|glacier|limnolog|hazard"),
    ("materials", r"material|nano|polymer|perovskite|semiconductor|metallurg|battery|catalys"),
    ("chemistry", r"chemi|molecul(e|ar) synthesis|organic synthesis|spectroscop"),
    ("physics", r"physic|quantum|optic|photon|laser|condensed matter|fluid|plasma|particle"),
    ("math_stats", r"mathemat|statist|topolog|algebra|geometr|probabil"),
    ("computing", r"comput|machine learning|artificial intelligence|\bai\b|algorithm|cyber|data science"),
    ("applied_tech", r"robot|biomedical eng|bioengineer|biotech|control system|energy science"),
    ("core_engineering", r"engineer|aerospace|civil|electrical|mechanical"),
    ("behavioral", r"psycholog|behaviou?ral science|cognit|mental health|psychiatr"),
    ("therapeutics", r"pharmac|drug|nursing|dentist|public health|epidemiolog|global health|vaccin"),
    ("clinical", r"medicine|clinical|oncolog|cancer|cardio|neurolog|alzheimer|infectious|disease|trial"),
    ("ecology", r"ecolog|conservation|biodivers|zoolog|plant|entomolog|insect|moth|bioinformatic|animal behaviou?r"),
    ("cell_molecular", r"cell biol|molecular|genetic|genom|biochem|structural biol"),
    ("organismal", r"neuro|immun|microbi|virolog|physiolog|developmental|evolution|palaeo|paleo|anthropolog"),
    ("social_economic", r"econom|financ|sociolog|politic|policy|educat|geograph"),
    ("resources", r"agricultur|forestry|food|veterinar|crop|water resource"),
]


def guess_topic(field: str, headline: str = "", journal: str = "") -> str | None:
    text = f"{field} | {headline} | {journal}".lower()
    for tid, pattern in KEYWORDS:
        if re.search(pattern, text):
            return tid
    return None


def _ai_topics(papers: list[dict]) -> list[str | None]:
    from . import ai
    schema = {
        "type": "object",
        "properties": {"topics": {"type": "array", "items": {"type": "string", "enum": TOPIC_IDS}}},
        "required": ["topics"],
        "additionalProperties": False,
    }
    listing = "\n".join(f"[{i}] {p['field']} | {p['journal']} | {p['headline']}" for i, p in enumerate(papers))
    data = ai._ask_json(
        "Assign each research paper to the single closest topic id from this list:\n" + prompt_list(),
        f"Return one topic id per paper, in order ({len(papers)} papers).\n\n{listing}",
        schema, effort="low", max_tokens=4000)
    topics = data.get("topics", [])
    return [topics[i] if i < len(topics) and topics[i] in TOPICS else None for i in range(len(papers))]


def backfill_topics(site: Path, use_ai: bool, log=print) -> int:
    """Tag untagged papers in every published digest. Returns how many were tagged."""
    data = site / "data"
    if not data.exists():
        return 0
    files, missing = {}, []
    for f in data.glob("*.json"):
        if f.stem in ("index", "latest", "topics", "search"):
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        files[f] = d
        missing += [p for p in d["papers"] if p.get("category") not in TOPICS]
    if not missing:
        return 0
    guesses = [None] * len(missing)
    if use_ai:
        try:
            guesses = _ai_topics(missing)
        except Exception as exc:
            log(f"  ! topic backfill with AI failed ({exc}); using keyword matching")
    for p, g in zip(missing, guesses):
        tid = g or guess_topic(p["field"], p["headline"], p["journal"])
        if tid:
            p["category"], p["category_name"] = tid, topic_name(tid)
            p.setdefault("editors_pick", True)
    for f, d in files.items():
        f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    done = sum(1 for p in missing if p.get("category") in TOPICS)
    log(f"  gave topics to {done} older paper(s)")
    return done
