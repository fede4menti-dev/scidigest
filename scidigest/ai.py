"""Claude-powered ranking and student-level paraphrasing."""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor

import anthropic

from .fetch import Article

MODEL = "claude-opus-5-5"
_client: anthropic.Anthropic | None = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _ask_json(system: str, prompt: str, schema: dict, effort: str = "medium",
              max_tokens: int = 16000) -> dict:
    resp = client().beta.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",  # if a safety classifier declines, retry on a suitable model
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("model declined this request")
    if resp.stop_reason == "max_tokens":
        raise RuntimeError("response was cut off (max_tokens)")
    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text)


# ---------------------------------------------------------------- ranking

RANK_SYSTEM = """You are the editor of a daily science digest for undergraduate science students.
From a list of newly published journal papers, choose the ones that matter most.

Judge significance by: how big a step forward it is for its field; how broadly it matters
(health, climate, technology, fundamental understanding); strength of evidence (large trials,
direct observation and replication beat small or preliminary studies); and novelty (a first, a
surprising result, or a long-standing question answered). Prefer variety across fields when
papers are close. Base your judgement only on the title and abstract provided; do not invent
details."""

RANK_SCHEMA = {
    "type": "object",
    "properties": {
        "picks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "score": {"type": "integer", "description": "significance 1-10"},
                    "field": {"type": "string", "description": "e.g. Astronomy, Neuroscience"},
                    "reason": {"type": "string", "description": "one sentence on why it was chosen"},
                },
                "required": ["index", "score", "field", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["picks"],
    "additionalProperties": False,
}


def rank(articles: list[Article], top: int) -> list[tuple[Article, dict]]:
    listing = "\n\n".join(
        f"[{i}] {a.journal}: {a.title}\n{a.abstract[:900]}" for i, a in enumerate(articles)
    )
    data = _ask_json(
        RANK_SYSTEM,
        f"Here are {len(articles)} new papers. Pick the {top} most significant, best first.\n\n{listing}",
        RANK_SCHEMA,
        effort="high",
    )
    picks, used = [], set()
    for p in data["picks"]:
        i = p["index"]
        if 0 <= i < len(articles) and i not in used:
            used.add(i)
            picks.append((articles[i], p))
    return picks[:top]


# ---------------------------------------------------------- summarising

SUMMARY_SYSTEM = """You explain new research papers to an average undergraduate science student:
someone who knows high-school biology, chemistry, physics and maths, but is not a specialist.

Rules:
- Paraphrase. Write everything in your own words. Never copy a phrase of more than six words from
  the source; if you must quote a technical term, define it.
- Stay faithful to the source. Use only facts stated in the text you are given (title, abstract,
  and full text when provided). Do
  not add numbers, methods, or claims that are not there. If the abstract is too thin to say
  something, say less rather than guess.
- Explain jargon the first time it appears, briefly and in plain words (or move it to key_terms).
- Be clear about certainty: say whether this is a first result, a model/simulation, an animal or
  cell study, a small or large human study, etc., when the abstract makes that clear.
- No hype words ("revolutionary", "breakthrough", "game-changer")."""

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string", "description": "plain-language headline, max ~12 words"},
        "summary": {"type": "string", "description": "2 short paragraphs: the question, what they did, what they found"},
        "why_it_matters": {"type": "string", "description": "2-3 sentences"},
        "key_terms": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"term": {"type": "string"}, "meaning": {"type": "string"}},
                "required": ["term", "meaning"],
                "additionalProperties": False,
            },
        },
        "limitations": {"type": "string", "description": "1-2 sentences on caveats or open questions; empty if the abstract gives no basis"},
    },
    "required": ["headline", "summary", "why_it_matters", "key_terms", "limitations"],
    "additionalProperties": False,
}


def _shingles(text: str, n: int = 8) -> set[tuple[str, ...]]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def copied_fraction(summary: str, source: str) -> float:
    """Share of 8-word runs in the summary that also appear in the source."""
    s = _shingles(summary)
    return len(s & _shingles(source)) / len(s) if s else 0.0


def summarize(article: Article, full_text: str = "", version: str = "",
              max_chars: int = 150_000, attempts: int = 2) -> dict:
    prompt = (f"Journal: {article.journal}\nTitle: {article.title}\n\n"
              f"Abstract / description from the publisher:\n{article.abstract or '(none provided)'}")
    note = ""
    if full_text:
        body = full_text[:max_chars]
        if len(full_text) > max_chars:
            note = f"(Full text shortened to its first {max_chars:,} characters.)"
        prompt += (f"\n\nFull text of a free, legal copy of this paper ({version}). Use it for "
                   f"concrete details such as methods, sample sizes and main results, but keep the "
                   f"summary short and readable. {note}\n<full_text>\n{body}\n</full_text>")
        if "Preprint" in version:
            prompt += ("\n\nThis copy is a preprint that had not been peer reviewed. Mention in "
                       "limitations that numbers in the final published paper may differ.")
    source = article.abstract + " " + full_text
    for _ in range(attempts):
        out = _ask_json(SUMMARY_SYSTEM, prompt, SUMMARY_SCHEMA)
        text = " ".join([out["summary"], out["why_it_matters"], out["limitations"]])
        out["copied_fraction"] = round(copied_fraction(text, source), 3)
        if out["copied_fraction"] < 0.08:
            break
        prompt += ("\n\nYour last draft reused too much of the original wording. Rewrite it fully "
                   "in your own words.")
    out["based_on"] = "full text" if full_text else "abstract"
    out["truncated"] = bool(note)
    return out


def summarize_many(jobs: list[tuple[Article, str, str]], workers: int = 4, **kw) -> list[dict]:
    """jobs: (article, full_text, version_label) tuples."""
    def safe(job):
        article = job[0]
        try:
            return summarize(*job, **kw)
        except Exception as exc:  # keep the rest of the report
            print(f"  ! summary failed for '{article.title[:60]}': {exc}")
            return {"headline": article.title,
                    "summary": article.abstract or "(No abstract available.)",
                    "why_it_matters": "A plain-language summary could not be generated for this paper today; "
                                      "the text above is the publisher's abstract.",
                    "key_terms": [], "limitations": "", "based_on": "abstract (not paraphrased)"}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(safe, jobs))
