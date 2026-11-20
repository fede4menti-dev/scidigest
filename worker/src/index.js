// Cloudflare Worker for the SciDigest idea checker.
//
//   GET  /health   -> {"ok": true, ...}
//   POST /check    {"question": "..."}  -> idea report JSON (see checker.js)
//
// Secrets (set by the GitHub deploy workflow): ANTHROPIC_API_KEY, OPENALEX_API_KEY (optional),
// APP_TOKEN (optional: if set, requests must send it in the X-App-Token header).
import Anthropic from "@anthropic-ai/sdk";
import { checkIdea, IdeaError } from "./checker.js";

const MODEL = "claude-opus-5-5";
const PER_IP_PER_HOUR = 10;

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, X-App-Token",
};

const json = (body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...CORS } });

// Best-effort limit per worker instance. The real safety net is a monthly spend
// limit on the Anthropic key (console.anthropic.com -> Billing -> Limits).
const hits = new Map();
function rateLimited(ip, now = Date.now()) {
  const recent = (hits.get(ip) || []).filter((t) => now - t < 3_600_000);
  if (recent.length >= PER_IP_PER_HOUR) return true;
  recent.push(now);
  hits.set(ip, recent);
  if (hits.size > 5000) hits.clear();
  return false;
}

export function makeClaude(client) {
  return async function claude(system, prompt, schema, effort) {
    const resp = await client.beta.messages.create({
      model: MODEL,
      max_tokens: 16000,
      betas: ["server-side-fallback-2026-07-01"],
      fallbacks: "default", // if a safety classifier declines, retry on a suitable model
      system,
      output_config: { effort, format: { type: "json_schema", schema } },
      messages: [{ role: "user", content: prompt }],
    });
    if (resp.stop_reason === "refusal") throw new IdeaError("This question couldn't be checked. Try rephrasing it.", 422);
    if (resp.stop_reason === "max_tokens") throw new IdeaError("The report was cut off. Please try again.", 502);
    const text = resp.content.find((b) => b.type === "text")?.text;
    if (!text) throw new IdeaError("Empty response from the model.", 502);
    return JSON.parse(text);
  };
}

export async function handle(request, env, deps = {}) {
  const url = new URL(request.url);
  if (request.method === "OPTIONS") return new Response(null, { headers: CORS });
  if (url.pathname === "/health") {
    return json({ ok: true, ai: Boolean(env.ANTHROPIC_API_KEY), openalex_key: Boolean(env.OPENALEX_API_KEY) });
  }
  if (url.pathname !== "/check" || request.method !== "POST") return json({ error: "Not found" }, 404);

  if (env.APP_TOKEN && request.headers.get("X-App-Token") !== env.APP_TOKEN) {
    return json({ error: "Not authorised." }, 401);
  }
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  if ((deps.rateLimited || rateLimited)(ip)) {
    return json({ error: `Limit reached: ${PER_IP_PER_HOUR} checks per hour. Please try again later.` }, 429);
  }
  if (!env.ANTHROPIC_API_KEY) return json({ error: "The idea checker isn't configured yet (no API key)." }, 503);

  let body;
  try {
    body = await request.json();
  } catch {
    return json({ error: "Send JSON like {\"question\": \"...\"}." }, 400);
  }

  try {
    const report = await checkIdea(body?.question, {
      claude: deps.claude || makeClaude(new Anthropic({ apiKey: env.ANTHROPIC_API_KEY })),
      fetch: deps.fetch || fetch,
      openAlexKey: env.OPENALEX_API_KEY,
    });
    return json(report);
  } catch (err) {
    if (err instanceof IdeaError) return json({ error: err.message }, err.status);
    if (err instanceof Anthropic.AuthenticationError) return json({ error: "The server's API key was rejected." }, 502);
    if (err instanceof Anthropic.RateLimitError) return json({ error: "Too busy right now. Try again in a minute." }, 503);
    if (err instanceof Anthropic.APIError) return json({ error: `AI service error (${err.status}). Try again shortly.` }, 502);
    console.error(err);
    return json({ error: "Something went wrong. Please try again." }, 500);
  }
}

export default {
  fetch: (request, env) => handle(request, env),
};
