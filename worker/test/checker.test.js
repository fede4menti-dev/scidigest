// Offline tests: Claude and the paper databases are faked.
import { test } from "node:test";
import assert from "node:assert/strict";
import { writeFileSync } from "node:fs";
import { abstractFromInverted, checkIdea, mergeResults, IdeaError } from "../src/checker.js";
import { handle } from "../src/index.js";

const OPENALEX = {
  results: [
    { id: "https://openalex.org/W1", doi: "https://doi.org/10.1/a", display_name: "Exercise and memory in older adults",
      publication_year: 2019, cited_by_count: 850, type: "article",
      authorships: [{ author: { display_name: "A. One" } }, { author: { display_name: "B. Two" } },
                    { author: { display_name: "C. Three" } }, { author: { display_name: "D. Four" } }],
      primary_location: { source: { display_name: "Neurology" } },
      abstract_inverted_index: { Aerobic: [0], exercise: [1], improved: [2], memory: [3] } },
    { id: "https://openalex.org/W2", doi: null, display_name: "Walking <i>and</i> cognition", publication_year: 2021,
      cited_by_count: 12, authorships: [], primary_location: { landing_page_url: "https://x.org/w2", source: null },
      abstract_inverted_index: null },
  ],
};
const EPMC = { resultList: { result: [
  { title: "Exercise and memory in older adults.", authorString: "One A, Two B", pubYear: "2019", doi: "10.1/a",
    citedByCount: 900, abstractText: "A much longer abstract about aerobic exercise improving memory in a trial.",
    journalInfo: { journal: { title: "Neurology" } }, source: "MED", id: "1" },
  { title: "Hippocampal volume after training", authorString: "Five E", pubYear: "2011", doi: "10.1/b",
    citedByCount: 3000, abstractText: "Training increased hippocampal volume.", journalInfo: { journal: { title: "PNAS" } },
    source: "MED", id: "2" },
] } };

function fakeFetch(calls) {
  return async (url, opts) => {
    calls.push({ url, headers: opts?.headers || {} });
    const body = url.includes("openalex") ? OPENALEX : EPMC;
    return { ok: true, status: 200, json: async () => body };
  };
}

function fakeClaude(log) {
  return async (system, prompt, schema, effort) => {
    log.push({ schema: Object.keys(schema.properties), effort, prompt });
    if (schema.properties.queries) {
      return { is_research_question: true, field: "Neuroscience",
               queries: ["exercise memory older adults", "aerobic training cognition aging", "exercise memory older adults"] };
    }
    return {
      verdict: "already well researched", novelty_score: 3, overall_score: 6,
      summary: "Several trials show exercise helps memory.",
      related: [{ index: 0, relevance: "directly addresses it", how_it_relates: "A trial of the same idea." },
                { index: 0, relevance: "closely related", how_it_relates: "duplicate, should be dropped" },
                { index: 99, relevance: "useful background", how_it_relates: "bad index, dropped" },
                { index: 1, relevance: "useful background", how_it_relates: "Brain structure changes." }],
      quality: Object.fromEntries(["clarity", "specificity", "feasibility", "significance", "testability"]
        .map((k) => [k, { score: 6, comment: `${k} ok` }])),
      ethics: "None stand out.", gaps: ["Dose of exercise"], suggestions: ["Name the age range"],
      improved_question: "Does 30 minutes of daily walking improve recall in adults over 65?",
    };
  };
}

test("rebuilds OpenAlex abstracts", () => {
  assert.equal(abstractFromInverted({ b: [1], a: [0], c: [2] }), "a b c");
  assert.equal(abstractFromInverted(null), "");
});

test("merge dedupes by DOI, counts hits and ranks relevance then citations", () => {
  const p = (doi, title, rank, cited, abstract = "") => ({ doi, title, rank, cited_by: cited, abstract });
  const merged = mergeResults([[p("10.1/a", "A", 0, 10), p(null, "B", 1, 5000)], [p("10.1/A", "A", 0, 20, "longer")]]);
  assert.equal(merged[0].title, "A");
  assert.equal(merged[0].cited_by, 20);
  assert.equal(merged[0].abstract, "longer");
  assert.equal(merged.length, 2);
  assert.ok(!("hits" in merged[0]) && !("rank" in merged[0]));
});

test("full check: queries, both sources, report shape", async () => {
  const calls = [], log = [];
  const report = await checkIdea("  Does regular aerobic exercise improve memory in older adults? ", {
    claude: fakeClaude(log), fetch: fakeFetch(calls), openAlexKey: "KEY", now: () => new Date("2026-11-20T00:00:00Z"),
  });
  assert.equal(log[0].effort, "low");
  assert.equal(log[1].effort, "medium");
  assert.equal(report.search.queries.length, 2, "duplicate query removed");
  assert.equal(calls.length, 4, "2 queries x 2 sources");
  assert.ok(calls.filter((c) => c.url.includes("openalex")).every((c) => c.headers.Authorization === "Bearer KEY"));
  assert.deepEqual(report.search.sources, ["Europe PMC", "OpenAlex"]);
  assert.equal(report.related.length, 2, "duplicate and out-of-range picks dropped");
  assert.equal(report.related[0].title, "Exercise and memory in older adults");
  assert.equal(report.related[0].cited_by, 900);
  assert.equal(report.related[0].authors, "A. One, B. Two, C. Three et al.");
  assert.ok(!("abstract" in report.related[0]));
  assert.equal(report.verdict, "already well researched");
  assert.equal(report.generated_at, "2026-11-20T00:00:00.000Z");
  writeFileSync(new URL("../../tests/fixtures/idea_report.json", import.meta.url), JSON.stringify(report, null, 1));
});

test("rejects non-questions and too-short text", async () => {
  const claude = async () => ({ is_research_question: false, field: "", queries: [] });
  await assert.rejects(checkIdea("hello there how are you today", { claude, fetch: fakeFetch([]) }), IdeaError);
  await assert.rejects(checkIdea("short", { claude, fetch: fakeFetch([]) }), /full sentence/);
});

test("one database down still works; both down gives 503", async () => {
  const halfDown = async (url) => url.includes("openalex")
    ? { ok: false, status: 429, json: async () => ({}) }
    : { ok: true, status: 200, json: async () => EPMC };
  const r = await checkIdea("Does exercise improve memory in older adults?", { claude: fakeClaude([]), fetch: halfDown });
  assert.deepEqual(r.search.sources, ["Europe PMC"]);
  assert.match(r.search.failures[0], /OpenAlex 429/);
  const down = async () => ({ ok: false, status: 500, json: async () => ({}) });
  await assert.rejects(checkIdea("Does exercise improve memory in older adults?", { claude: fakeClaude([]), fetch: down }),
    (e) => e.status === 503);
});

test("HTTP handler: routes, token, rate limit, errors", async () => {
  const env = { ANTHROPIC_API_KEY: "k", APP_TOKEN: "t" };
  const deps = { claude: fakeClaude([]), fetch: fakeFetch([]), rateLimited: () => false };
  const post = (body, headers = { "X-App-Token": "t" }) =>
    new Request("https://w.dev/check", { method: "POST", body, headers: { "Content-Type": "application/json", ...headers } });

  assert.equal((await handle(new Request("https://w.dev/health"), env)).status, 200);
  assert.equal((await handle(new Request("https://w.dev/nope"), env)).status, 404);
  assert.equal((await handle(post("{}", {}), env, deps)).status, 401);
  assert.equal((await handle(post("not json"), env, deps)).status, 400);
  assert.equal((await handle(post(JSON.stringify({ question: "hi" })), env, deps)).status, 400);
  const ok = await handle(post(JSON.stringify({ question: "Does exercise improve memory in older adults?" })), env, deps);
  assert.equal(ok.status, 200);
  assert.equal(ok.headers.get("Access-Control-Allow-Origin"), "*");
  assert.equal((await ok.json()).verdict, "already well researched");
  const limited = await handle(post(JSON.stringify({ question: "x" })), env, { ...deps, rateLimited: () => true });
  assert.equal(limited.status, 429);
  assert.equal((await handle(post("{}"), { APP_TOKEN: "t" }, deps)).status, 503, "no API key configured");
});
