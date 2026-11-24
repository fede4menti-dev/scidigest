"""The daily run's requests go through the half-price Batches API, with safe fallbacks."""
import json
from types import SimpleNamespace as NS

import pytest

from scidigest import ai
from scidigest.fetch import Article
from scidigest.fulltext import jats_to_text

SUMMARY = {"headline": "h", "summary": "A summary written entirely in new words for students.",
           "why_it_matters": "w", "key_terms": [], "limitations": "", "figure_index": -1,
           "figure_caption": "", "image_query": "q"}


def msg(payload, inp=10_000, out=2_000, stop="end_turn"):
    return NS(stop_reason=stop, content=[NS(type="text", text=json.dumps(payload))],
              usage=NS(input_tokens=inp, output_tokens=out))


class FakeBatches:
    def __init__(self, outcomes, ends_after=0):
        self.outcomes, self.ends_after, self.polls = outcomes, ends_after, 0
        self.sent, self.cancelled = None, False

    def create(self, requests):
        self.sent = requests
        return NS(id="b1", processing_status="in_progress")

    def retrieve(self, bid):
        self.polls += 1
        done = self.cancelled or self.polls > self.ends_after
        return NS(id=bid, processing_status="ended" if done else "in_progress")

    def cancel(self, bid):
        self.cancelled = True

    def results(self, bid):
        for r in self.sent:
            kind = self.outcomes.get(r["custom_id"], "missing")
            if kind == "ok":
                yield NS(custom_id=r["custom_id"], result=NS(type="succeeded", message=msg(SUMMARY)))
            elif kind in ("errored", "expired"):
                yield NS(custom_id=r["custom_id"], result=NS(type=kind))


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setenv("SCIDIGEST_BATCH", "1")
    monkeypatch.setattr(ai, "POLL_SECONDS", 0)
    monkeypatch.setattr(ai, "_usage", {k: 0 for k in ai._usage})
    standard_calls = []

    def make(outcomes, ends_after=0):
        batches = FakeBatches(outcomes, ends_after)
        def create(**kw):
            standard_calls.append(kw)
            return msg(SUMMARY)
        client = NS(messages=NS(batches=batches), beta=NS(messages=NS(create=create)))
        monkeypatch.setattr(ai, "client", lambda: client)
        return batches, standard_calls
    return make


def art(i):
    return Article(id=str(i), title=f"T{i}", journal="J", link="", abstract="An abstract. " * 5, published=None)


def test_summaries_go_through_one_batch_and_failures_are_redone(fake):
    batches, standard = fake({"0": "ok", "1": "errored", "2": "ok"})
    out = ai.summarize_many([(art(i), "", "", []) for i in range(3)])
    assert len(batches.sent) == 3
    params = batches.sent[0]["params"]
    assert params["model"] == ai.MODEL and "fallbacks" not in params            # batches can't use fallbacks
    assert params["output_config"]["format"]["type"] == "json_schema"
    assert all(o["headline"] == "h" for o in out)
    assert len(standard) == 1 and standard[0]["fallbacks"] == "default"       # only the failed one, normally
    assert ai._usage["batch_calls"] == 2 and ai._usage["calls"] == 1
    # 2 batch calls at half price + 1 normal call, each 10k in / 2k out on Opus 5.5
    assert abs(ai.spent_usd() - (2 * 0.5 + 1) * (10_000 * 4 + 2_000 * 20) / 1e6) < 1e-9


def test_slow_batch_is_cancelled_and_finished_normally(fake, monkeypatch):
    monkeypatch.setenv("SCIDIGEST_BATCH_WAIT_MIN", "0")
    batches, standard = fake({"0": "ok"}, ends_after=10**6)
    out = ai.summarize_many([(art(i), "", "", []) for i in range(2)])
    assert batches.cancelled and all(o and o["headline"] == "h" for o in out)
    assert len(standard) == 1                                                  # the unfinished one


def test_spending_cap_trims_the_batch_before_sending(fake, monkeypatch):
    monkeypatch.setenv("SCIDIGEST_MAX_RUN_USD", "0.05")
    batches, _ = fake({"0": "ok", "1": "ok", "2": "ok"})
    out = ai.summarize_many([(art(i), "x" * 20_000, "Published version", []) for i in range(3)], max_chars=20_000)
    assert len(batches.sent) < 3 and out[-1] is None                           # last (topic) pick dropped


def test_ranking_uses_batch_price_and_falls_back(fake):
    batches, standard = fake({"only": "ok"})
    assert ai.ask_json_cheap("s", "p", {"type": "object"}) == SUMMARY and not standard
    batches, standard = fake({"only": "errored"})
    assert ai.ask_json_cheap("s", "p", {"type": "object"}) == SUMMARY and len(standard) == 1


def test_full_text_puts_results_and_conclusions_first():
    xml = b"""<article><body>
      <sec><title>Introduction</title><p>INTRO</p></sec>
      <sec><title>Methods</title><p>METHODS</p></sec>
      <sec><title>Results</title><p>RESULTS</p></sec>
      <sec><title>Discussion</title><p>DISCUSSION</p></sec></body></article>"""
    t = jats_to_text(xml)
    assert t.index("RESULTS") < t.index("DISCUSSION") < t.index("INTRO") < t.index("METHODS")
