// Idea checker: has this research question already been studied, and how good is it?
//
// 1. Claude turns the question into a few literature-search queries.
// 2. OpenAlex (all fields, ~250M works) and Europe PMC (life sciences) are searched.
// 3. Results are merged and the most important ones kept (relevance across queries + citations).
// 4. Claude writes a report: how much is already known, the closest papers, and a quality
//    review of the question itself (clarity, specificity, feasibility, significance, testability).
//
// Everything external is passed in via `deps`, so this file runs unchanged in tests.

export const MAX_QUESTION = 1500;
const MAX_CANDIDATES = 22;   // papers Claude reads closely (kept small: input is the main cost)
const MAX_RELATED = 10;      // papers shown in the report

// ---------------------------------------------------------------- prompts

export const PLAN_SYSTEM = `You help students check research ideas against the published literature.
Given a research question, write literature-search queries that would find existing work on it.
Queries are short keyword phrases (3 to 8 words) like a researcher would type into a paper database:
one close to the exact question, one broader, and one or two using alternative technical terms.
If the text is not a research question or idea at all, set is_research_question to false.`;

export const PLAN_SCHEMA = {
  type: "object",
  properties: {
    is_research_question: { type: "boolean" },
    field: { type: "string", description: "main research field, e.g. Neuroscience" },
    queries: { type: "array", items: { type: "string" }, description: "3 or 4 search queries" },
  },
  required: ["is_research_question", "field", "queries"],
  additionalProperties: false,
};

export const REPORT_SYSTEM = `You review research questions for undergraduate science students.
You are given a student's research question and the most relevant papers found in OpenAlex and
Europe PMC (title, year, venue, citation count, abstract). Write an honest, encouraging report in
plain language a science student understands.

1. Prior research: decide how much of the question is already answered by these papers.
   Only claim something has been studied if a listed paper actually shows it; never invent papers
   or findings. The search covers a limited set of results, so "little prior research found" means
   "not found in this search", not "proven new"; say so in the summary when relevant.
2. Related papers: choose up to ${MAX_RELATED} of the listed papers that matter most for this question,
   most important first. Judge relevance from what each paper actually studied (its abstract), not from
   shared words: papers often use different terms for the same thing (e.g. "physical activity" for
   "exercise", "cognition" for "memory"), and a paper can share words with the question but be about
   something else. Only include a paper if it genuinely helps answer, test or frame this question; if it
   is only loosely connected, leave it out. It is fine to return fewer papers, or none.
   For each paper write one specific sentence (max ~30 words) saying what it found or did and how that
   connects to the student's idea, naming the shared variable, population or method. If the paper uses
   different wording for the same concept, say so briefly. Never write generic phrases like "related
   to the topic".
3. Quality of the question: score 1 to 10 and comment briefly on clarity (is it unambiguous),
   specificity (are variables, population and scope defined), feasibility (could a student or small
   lab realistically study it, with what data or methods), significance (why the answer would matter)
   and testability (can it be answered with evidence). Note ethical issues if any, else say none stand out.
4. Gaps and next steps: what the existing work leaves open, concrete suggestions to make the question
   sharper or more original, and one improved version of the question.`;

const scored = (what) => ({
  type: "object",
  properties: {
    score: { type: "integer", description: `1-10 for ${what}` },
    comment: { type: "string", description: "one or two sentences" },
  },
  required: ["score", "comment"],
  additionalProperties: false,
});

export const REPORT_SCHEMA = {
  type: "object",
  properties: {
    verdict: {
      type: "string",
      enum: ["already well researched", "partly researched", "little prior research found"],
    },
    novelty_score: { type: "integer", description: "1-10, 10 = no prior work found on this exact question" },
    summary: { type: "string", description: "2-4 sentences: what is already known and what is not" },
    related: {
      type: "array",
      items: {
        type: "object",
        properties: {
          index: { type: "integer" },
          relevance: { type: "string", enum: ["directly addresses it", "closely related", "useful background"] },
          how_it_relates: { type: "string", description: "one specific sentence: what the paper found or did, and how it connects to the student's idea" },
        },
        required: ["index", "relevance", "how_it_relates"],
        additionalProperties: false,
      },
    },
    quality: {
      type: "object",
      properties: {
        clarity: scored("clarity"),
        specificity: scored("specificity"),
        feasibility: scored("feasibility"),
        significance: scored("significance"),
        testability: scored("testability"),
      },
      required: ["clarity", "specificity", "feasibility", "significance", "testability"],
      additionalProperties: false,
    },
    overall_score: { type: "integer", description: "1-10 overall quality of the research question" },
    ethics: { type: "string" },
    gaps: { type: "array", items: { type: "string" } },
    suggestions: { type: "array", items: { type: "string" } },
    improved_question: { type: "string" },
  },
  required: ["verdict", "novelty_score", "summary", "related", "quality", "overall_score",
             "ethics", "gaps", "suggestions", "improved_question"],
  additionalProperties: false,
};

// ---------------------------------------------------------------- search

const clean = (s) => String(s || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();

export function abstractFromInverted(inv) {
  if (!inv) return "";
  const words = [];
  for (const [word, positions] of Object.entries(inv)) for (const p of positions) words[p] = word;
  return words.filter(Boolean).join(" ");
}

function authorLine(names) {
  const n = names.filter(Boolean);
  if (n.length === 0) return "";
  if (n.length <= 3) return n.join(", ");
  return `${n.slice(0, 3).join(", ")} et al.`;
}

export async function searchOpenAlex(query, { fetch, openAlexKey, perPage = 15 }) {
  const url = new URL("https://api.openalex.org/works");
  url.searchParams.set("search", query);
  url.searchParams.set("per_page", String(perPage));
  url.searchParams.set("select",
    "id,doi,display_name,publication_year,cited_by_count,authorships,primary_location,abstract_inverted_index,type");
  const headers = { "User-Agent": "SciDigest-IdeaChecker/1.0" };
  if (openAlexKey) headers.Authorization = `Bearer ${openAlexKey}`;
  const r = await fetch(url.toString(), { headers });
  if (!r.ok) throw new Error(`OpenAlex ${r.status}`);
  const data = await r.json();
  return (data.results || []).map((w, rank) => ({
    title: clean(w.display_name),
    authors: authorLine((w.authorships || []).map((a) => a.author?.display_name)),
    year: w.publication_year ?? null,
    venue: w.primary_location?.source?.display_name || "",
    doi: w.doi ? w.doi.replace(/^https?:\/\/doi\.org\//i, "") : null,
    url: w.doi || w.primary_location?.landing_page_url || w.id,
    cited_by: w.cited_by_count ?? 0,
    abstract: abstractFromInverted(w.abstract_inverted_index).slice(0, 1500),
    source: "OpenAlex",
    rank,
  }));
}

export async function searchEuropePMC(query, { fetch, pageSize = 10 }) {
  const url = new URL("https://www.ebi.ac.uk/europepmc/webservices/rest/search");
  url.searchParams.set("query", query);
  url.searchParams.set("format", "json");
  url.searchParams.set("resultType", "core");
  url.searchParams.set("pageSize", String(pageSize));
  const r = await fetch(url.toString(), { headers: { "User-Agent": "SciDigest-IdeaChecker/1.0" } });
  if (!r.ok) throw new Error(`Europe PMC ${r.status}`);
  const data = await r.json();
  return (data.resultList?.result || []).map((w, rank) => ({
    title: clean(w.title).replace(/\.$/, ""),
    authors: authorLine(String(w.authorString || "").split(",").map((s) => s.trim())),
    year: w.pubYear ? Number(w.pubYear) : null,
    venue: w.journalInfo?.journal?.title || w.bookOrReportDetails?.publisher || "",
    doi: w.doi || null,
    url: w.doi ? `https://doi.org/${w.doi}` : `https://europepmc.org/article/${w.source}/${w.id}`,
    cited_by: w.citedByCount ?? 0,
    abstract: clean(w.abstractText).slice(0, 1500),
    source: "Europe PMC",
    rank,
  }));
}

/** Merge results from all queries/sources, keeping the most important papers. */
export function mergeResults(lists, limit = MAX_CANDIDATES) {
  const byKey = new Map();
  for (const list of lists) {
    for (const p of list) {
      const key = (p.doi || p.title).toLowerCase().replace(/[^a-z0-9./]/g, "");
      if (!key || !p.title) continue;
      const cur = byKey.get(key);
      if (!cur) {
        byKey.set(key, { ...p, hits: 1, bestRank: p.rank });
      } else {
        cur.hits += 1;
        cur.bestRank = Math.min(cur.bestRank, p.rank);
        cur.cited_by = Math.max(cur.cited_by, p.cited_by);
        if (p.abstract.length > cur.abstract.length) cur.abstract = p.abstract;
        if (!cur.doi && p.doi) cur.doi = p.doi;
      }
    }
  }
  // Relevance (found by several queries, high in results) first, then citation impact.
  const score = (p) => p.hits * 3 + (15 - Math.min(p.bestRank, 15)) * 0.4 + Math.log10(p.cited_by + 1);
  return [...byKey.values()]
    .sort((a, b) => score(b) - score(a))
    .slice(0, limit)
    .map(({ rank, bestRank, hits, ...p }) => p);
}

// ---------------------------------------------------------------- main

export class IdeaError extends Error {
  constructor(message, status = 400) {
    super(message);
    this.status = status;
  }
}

/**
 * deps: { claude(system, prompt, schema, effort) -> object, fetch, openAlexKey?, now? }
 */
export async function checkIdea(question, deps) {
  question = clean(question);
  if (question.length < 15) throw new IdeaError("Please write your research question in a full sentence.");
  if (question.length > MAX_QUESTION) throw new IdeaError(`Please keep the question under ${MAX_QUESTION} characters.`);

  const plan = await deps.claude(PLAN_SYSTEM, `Research question: ${question}`, PLAN_SCHEMA, "low");
  if (!plan.is_research_question) {
    throw new IdeaError("That doesn't look like a research question. Try something like: " +
      "\"Does daily exercise improve memory in older adults?\"");
  }
  const queries = [...new Set((plan.queries || []).map(clean).filter(Boolean))].slice(0, 4);
  if (queries.length === 0) queries.push(question.slice(0, 200));

  const sources = new Set();
  const failures = [];
  const jobs = [];
  for (const q of queries) {
    jobs.push(searchOpenAlex(q, deps).then((r) => { sources.add("OpenAlex"); return r; }));
    jobs.push(searchEuropePMC(q, deps).then((r) => { sources.add("Europe PMC"); return r; }));
  }
  const settled = await Promise.allSettled(jobs);
  const lists = [];
  for (const s of settled) {
    if (s.status === "fulfilled") lists.push(s.value);
    else failures.push(String(s.reason?.message || s.reason));
  }
  const candidates = mergeResults(lists);
  if (candidates.length === 0) {
    throw new IdeaError("The paper databases couldn't be searched right now. Please try again in a few minutes.", 503);
  }

  const listing = candidates.map((p, i) =>
    `[${i}] ${p.title} (${p.year ?? "n.d."}; ${p.venue || "unknown venue"}; cited ${p.cited_by} times)\n` +
    (p.abstract ? p.abstract.slice(0, 650) : "(no abstract available)")).join("\n\n");
  const report = await deps.claude(
    REPORT_SYSTEM,
    `Student's research question: ${question}\n\nField: ${plan.field}\n\n` +
      `The ${candidates.length} most relevant papers found:\n\n${listing}`,
    REPORT_SCHEMA,
    "medium",
  );

  const seen = new Set();
  const related = [];
  for (const r of report.related || []) {
    const p = candidates[r.index];
    if (!p || seen.has(r.index)) continue;
    seen.add(r.index);
    const { abstract, ...meta } = p;
    related.push({ ...meta, relevance: r.relevance, how_it_relates: r.how_it_relates });
    if (related.length >= MAX_RELATED) break;
  }

  return {
    question,
    field: plan.field,
    verdict: report.verdict,
    novelty_score: report.novelty_score,
    overall_score: report.overall_score,
    summary: report.summary,
    quality: report.quality,
    ethics: report.ethics,
    gaps: report.gaps,
    suggestions: report.suggestions,
    improved_question: report.improved_question,
    related,
    search: { queries, sources: [...sources].sort(), papers_considered: candidates.length, failures },
    generated_at: (deps.now ? deps.now() : new Date()).toISOString(),
  };
}
