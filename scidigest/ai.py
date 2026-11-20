"""Claude-powered ranking and student-level paraphrasing."""
from __future__ import annotations

import json
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor

import anthropic

from .fetch import Article
from .taxonomy import TOPIC_IDS, TOPICS, prompt_list

MODEL = "claude-opus-5-5"
_client: anthropic.Anthropic | None = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        key = os.environ.get("ANTHROPIC_API_KEY", "").strip().strip('"').strip("'")
        # Strip stray spaces, newlines or quotes that sneak in when pasting a secret.
        _client = anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()
    return _client


# ------------------------------------------------------------ spending guard
# Claude Opus 5.5 list prices, USD per million tokens (thinking is billed as output).
PRICE_IN, PRICE_OUT = 4.00, 20.00
_usage = {"input": 0, "output": 0, "calls": 0}
_usage_lock = threading.Lock()


class BudgetExceeded(RuntimeError):
    pass


def budget_usd() -> float:
    """Hard cap for one run (SCIDIGEST_MAX_RUN_USD, default $4). 0 or less = no cap."""
    try:
        return float(os.environ.get("SCIDIGEST_MAX_RUN_USD", "4"))
    except ValueError:
        return 4.0


def spent_usd() -> float:
    return (_usage["input"] * PRICE_IN + _usage["output"] * PRICE_OUT) / 1_000_000


def usage_line() -> str:
    return (f"Claude usage this run: {_usage['calls']} calls, {_usage['input']:,} input + "
            f"{_usage['output']:,} output tokens, about ${spent_usd():.2f} (cap ${budget_usd():.2f})")


def _record(resp) -> None:
    u = getattr(resp, "usage", None)
    if u is None:
        return
    with _usage_lock:
        _usage["calls"] += 1
        _usage["input"] += (getattr(u, "input_tokens", 0) or 0) + (getattr(u, "cache_creation_input_tokens", 0) or 0)
        _usage["output"] += getattr(u, "output_tokens", 0) or 0


def check_budget() -> None:
    cap = budget_usd()
    if cap > 0 and spent_usd() >= cap:
        raise BudgetExceeded(f"run budget of ${cap:.2f} reached")


def _ask_json(system: str, prompt: str, schema: dict, effort: str = "medium",
              max_tokens: int = 16000) -> dict:
    check_budget()
    resp = client().beta.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",  # if a safety classifier declines, retry on a suitable model
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    _record(resp)
    if resp.stop_reason == "refusal":
        raise RuntimeError("model declined this request")
    if resp.stop_reason == "max_tokens":
        raise RuntimeError("response was cut off (max_tokens)")
    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text)


# ---------------------------------------------------------------- ranking

RANK_SYSTEM = """You are the editor of a daily science digest for undergraduate science students.
From a list of recent journal papers, choose the ones that matter most today.

Judge significance by: how big a step forward it is for its field; how broadly it matters
(health, climate, technology, fundamental understanding); strength of evidence (large trials,
direct observation and replication beat small or preliminary studies); and novelty (a first, a
surprising result, or a long-standing question answered). Prefer variety across fields when
papers are close. Base your judgement only on the title and abstract provided; do not invent
details.

Freshness: papers from the last two days are the default choice. An older paper (up to two weeks)
can be picked if it is clearly more important than the new ones, or especially relevant on today's
date (for example tied to the season, a recurring event, or a topic with obvious public attention
at this time of year). Most of each day's picks should be new.

Repeats: a paper marked "already featured" may be picked again only if it is exceptionally
important (one of the standout papers of the month), and at most for one or two slots per day.

Only choose original research or major reviews. Skip anything that is a letter, correspondence,
commentary, editorial, news item, or correction, and skip items whose abstract is missing or only
gives citation details, since readers need real findings."""

RANK_SCHEMA_TEMPLATE = {
    "type": "object",
    "properties": {
        "selections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "topic": {"type": "string", "enum": TOPIC_IDS},
                    "editors_pick": {"type": "boolean"},
                    "score": {"type": "integer", "description": "significance 1-10"},
                    "field": {"type": "string", "description": "specific field label, e.g. Astrophysics, Immunology"},
                    "reason": {"type": "string", "description": "one sentence on why it was chosen (mention timeliness if that was the reason)"},
                },
                "required": ["index", "topic", "editors_pick", "score", "field", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["selections"],
    "additionalProperties": False,
}
RANK_SCHEMA = RANK_SCHEMA_TEMPLATE

TOPIC_RULES = """Readers follow topics. Assign every paper you select to exactly one topic id from this list
(the closest fit):
{topics}

Make two kinds of selection in one list:
- Editor's picks (editors_pick = true): exactly {top} papers, the most significant overall today, any topic,
  best first.
- Topic picks (editors_pick = false): for EACH topic, up to {per_topic} of the best remaining papers in that
  topic, so readers who only follow that topic still get good papers. Skip a topic if nothing in it is
  worth reading; never pad with weak papers. A paper appears at most once in the list.

Preprints (marked "preprint, not peer reviewed") are the main venue for mathematics, computer science,
statistics and economics, so they are welcome as topic picks there; be stricter with them as editor's picks."""


def _age(a: Article, today) -> str:
    if not a.published:
        return "publication date not listed"
    days = (today - a.published.date()).days
    when = a.published.date().isoformat()
    return f"published {when} ({'today' if days <= 0 else f'{days} day' + ('s' if days != 1 else '') + ' ago'})"


def rank(articles: list[Article], top: int, today=None, featured: dict | None = None,
         per_topic: int = 2) -> list[tuple[Article, dict]]:
    """Returns editor's picks first (in order), then topic picks (by score).
    featured: index -> list of dates the paper was already a daily pick."""
    from datetime import date as _date
    today = today or _date.today()
    featured = featured or {}
    snippet = 900 if len(articles) <= 150 else 600
    lines = []
    for i, a in enumerate(articles):
        note = f" | already featured on {', '.join(featured[i])}" if featured.get(i) else ""
        kind = " | preprint, not peer reviewed" if getattr(a, "preprint", False) else ""
        lines.append(f"[{i}] {a.journal}: {a.title}\n({_age(a, today)}{kind}{note})\n{a.abstract[:snippet]}")
    system = RANK_SYSTEM + "\n\n" + TOPIC_RULES.format(topics=prompt_list(), top=top, per_topic=per_topic)
    data = _ask_json(
        system,
        f"Today is {today:%A, %B %d, %Y}. Here are {len(articles)} recent papers. Make today's selections.\n\n"
        + "\n\n".join(lines),
        RANK_SCHEMA,
        effort="high",
    )
    editors, others, used = [], [], set()
    for p in data["selections"]:
        i = p["index"]
        if not (0 <= i < len(articles)) or i in used or p.get("topic") not in TOPICS:
            continue
        used.add(i)
        (editors if p.get("editors_pick") and len(editors) < top else others).append((articles[i], p))
    for _, p in others:
        p["editors_pick"] = False
    # Keep at most per_topic topic picks per topic.
    kept, count = [], {}
    for a, p in sorted(others, key=lambda x: -x[1].get("score", 0)):
        if count.get(p["topic"], 0) < per_topic:
            count[p["topic"]] = count.get(p["topic"], 0) + 1
            kept.append((a, p))
    return editors + kept


# -------------------------------------------------------- weekly/monthly

REVIEW_SYSTEM = """You are the editor of a science digest for undergraduate science students, writing
the {span} review. You get every paper that appeared in the daily digests during the {span}, each with
its topic and plain-language summary. Choose the most important ones: the biggest advances, the
strongest evidence and the widest relevance, with variety across fields when papers are close.
Mark exactly {top} as editor's picks (the most important overall, best first). Then, for each topic,
add up to {per_topic} more of its best papers as topic picks (editors_pick = false), so readers who
follow only that topic get a good review too; skip topics with nothing strong.
Then write a short overview (3 to 5 sentences) that tells a student what the {span} in science looked
like: the main themes and the standout results, in plain language, without hype and without
introducing any facts that are not in the summaries."""

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "intro": {"type": "string", "description": "3-5 sentence overview of the period"},
        "picks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "editors_pick": {"type": "boolean"},
                    "score": {"type": "integer", "description": "significance 1-10"},
                    "reason": {"type": "string", "description": "one sentence on why it is one of the most important of the period"},
                },
                "required": ["index", "editors_pick", "score", "reason"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["intro", "picks"],
    "additionalProperties": False,
}


def rank_review(papers: list[dict], top: int, span: str, label: str,
                per_topic: int = 2) -> tuple[str, list[tuple[dict, dict]]]:
    """papers are published paper JSON objects. Returns (intro, [(paper, pick)]), editor's picks first."""
    listing = "\n\n".join(
        f"[{i}] topic: {p.get('category') or 'unassigned'} | {p['field']} | {p['journal']} | "
        f"daily significance {p['significance']}/10\n"
        f"{p['headline']}\n{p['summary'][:1200]}\nWhy it matters: {p['why_it_matters']}"
        for i, p in enumerate(papers))
    data = _ask_json(
        REVIEW_SYSTEM.format(span=span, top=top, per_topic=per_topic),
        f"The {span}: {label}. Here are the {len(papers)} papers featured. "
        f"Make the selections and write the overview.\n\n{listing}",
        REVIEW_SCHEMA,
        effort="high",
    )
    editors, others, used = [], [], set()
    for p in data["picks"]:
        i = p["index"]
        if 0 <= i < len(papers) and i not in used:
            used.add(i)
            (editors if p.get("editors_pick") and len(editors) < top else others).append((papers[i], p))
    for _, p in others:
        p["editors_pick"] = False
    kept, count = [], {}
    for paper, p in sorted(others, key=lambda x: -x[1].get("score", 0)):
        t = paper.get("category") or "_"
        if count.get(t, 0) < per_topic:
            count[t] = count.get(t, 0) + 1
            kept.append((paper, p))
    return data["intro"], editors + kept


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
        "figure_index": {"type": "integer", "description": "index of the paper figure that best shows the main finding, or -1 if no figures are listed or none is clear enough for a student"},
        "figure_caption": {"type": "string", "description": "plain-language caption (1-2 sentences) for that figure, based only on its original caption; empty if figure_index is -1"},
        "image_query": {"type": "string", "description": "2-4 word search for a real photo of the paper's subject (an organism, object, place or instrument), e.g. 'malaria mosquito', 'perovskite solar panel', 'radio telescope'. Avoid abstract concepts."},
    },
    "required": ["headline", "summary", "why_it_matters", "key_terms", "limitations",
                 "figure_index", "figure_caption", "image_query"],
    "additionalProperties": False,
}


def _shingles(text: str, n: int = 8) -> set[tuple[str, ...]]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def copied_fraction(summary: str, source: str) -> float:
    """Share of 8-word runs in the summary that also appear in the source."""
    s = _shingles(summary)
    return len(s & _shingles(source)) / len(s) if s else 0.0


def summarize(article: Article, full_text: str = "", version: str = "", figures: list | None = None,
              max_chars: int = 150_000, attempts: int = 2) -> dict:
    prompt = (f"Journal: {article.journal}\nTitle: {article.title}\n\n"
              f"Abstract / description from the publisher:\n{article.abstract or '(none provided)'}")
    if getattr(article, "preprint", False):
        prompt += ("\n\nThis is a preprint that has not been peer reviewed yet. Say so briefly in the "
                   "summary or limitations.")
    if figures:
        prompt += "\n\nFigures available from the paper (choose one with figure_index, or -1):\n" + "\n".join(
            f"[{i}] {f.get('label', '')}: {f.get('caption', '')[:500]}" for i, f in enumerate(figures))
    else:
        prompt += "\n\nNo figures are available for this paper: set figure_index to -1 and figure_caption to empty."
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
    """jobs: (article, full_text, version_label, figures) tuples."""
    def safe(job):
        article = job[0]
        try:
            return summarize(*job, **kw)
        except BudgetExceeded:
            return None           # caller drops (topic picks) or quotes the abstract (editor's picks)
        except Exception as exc:  # keep the rest of the report
            print(f"  ! summary failed for '{article.title[:60]}': {exc}")
            return {"headline": article.title,
                    "summary": article.abstract or "(No abstract available.)",
                    "why_it_matters": "A plain-language summary could not be generated for this paper today; "
                                      "the text above is the publisher's abstract.",
                    "key_terms": [], "limitations": "", "based_on": "abstract (not paraphrased)",
                    "figure_index": -1, "figure_caption": "", "image_query": ""}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(safe, jobs))
