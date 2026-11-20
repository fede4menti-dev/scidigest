// Cloudflare Worker for SciDigest: idea checker + reader accounts.
//
//   GET    /health                -> {"ok": true, ...}
//   POST   /check                 {"question"}            -> idea report (see checker.js)
//   POST   /auth/signup           {"email","password","data"?} -> {token, recovery_code, account}
//   POST   /auth/login            {"email","password"}    -> {token, account}
//   POST   /auth/reset            {"email","recovery_code","new_password"} -> {token, recovery_code, account}
//   GET    /me                    (Authorization: Bearer)  -> {email, created, updated, data}
//   PUT    /me/data               {"data"}                 -> {updated}
//   POST   /me/delete             {"password"}             -> {deleted}
//
// Secrets (set by the deploy workflow): ANTHROPIC_API_KEY, OPENALEX_API_KEY (optional),
// APP_TOKEN (optional: idea checks must send it in X-App-Token).
// Bindings: DATA (KV) for accounts, the idea-check cache and the daily counter.
// Vars: DAILY_CHECK_LIMIT (default 150 idea checks per day for the whole site).
import Anthropic from "@anthropic-ai/sdk";
import { checkIdea, IdeaError } from "./checker.js";
import { AccountError, deleteAccount, getMe, login, putData, resetPassword, signup } from "./accounts.js";

const MODEL = "claude-opus-5-5";
const PER_IP_PER_HOUR = 10;          // idea checks per person per hour
const AUTH_PER_IP_PER_10MIN = 20;    // sign-in attempts, to slow password guessing
const CACHE_DAYS = 30;               // same question again -> cached report, no AI cost

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, PUT, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, X-App-Token",
};

const json = (body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...CORS } });

// Best-effort limits per worker instance (cheap, no storage writes).
function limiter(max, windowMs) {
  const hits = new Map();
  return (ip, now = Date.now()) => {
    const recent = (hits.get(ip) || []).filter((t) => now - t < windowMs);
    if (recent.length >= max) return true;
    recent.push(now);
    hits.set(ip, recent);
    if (hits.size > 5000) hits.clear();
    return false;
  };
}
const ideaLimited = limiter(PER_IP_PER_HOUR, 3_600_000);
const authLimited = limiter(AUTH_PER_IP_PER_10MIN, 600_000);

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

async function questionKey(question) {
  const norm = String(question || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(norm));
  return "idea:" + [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 40);
}

const today = () => new Date().toISOString().slice(0, 10);

async function handleCheck(request, env, deps) {
  if (env.APP_TOKEN && request.headers.get("X-App-Token") !== env.APP_TOKEN) {
    return json({ error: "Not authorised." }, 401);
  }
  if (!env.ANTHROPIC_API_KEY) return json({ error: "The idea checker isn't configured yet (no API key)." }, 503);
  const body = await request.json().catch(() => null);
  if (!body) return json({ error: "Send JSON like {\"question\": \"...\"}." }, 400);

  const kv = env.DATA;
  const cacheKey = kv ? await questionKey(body.question) : null;
  if (kv) {
    const cached = await kv.get(cacheKey, "json");
    if (cached) return json({ ...cached, cached: true });   // free: no AI call
  }

  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  if ((deps.rateLimited || ideaLimited)(ip)) {
    return json({ error: `Limit reached: ${PER_IP_PER_HOUR} checks per hour. Please try again later.` }, 429);
  }
  const dailyLimit = Number(env.DAILY_CHECK_LIMIT || 150);
  const counterKey = `count:${today()}`;
  if (kv) {
    const used = Number((await kv.get(counterKey)) || 0);
    if (used >= dailyLimit) {
      return json({ error: "Idea Check has reached today's limit for the whole site. Please try again tomorrow." }, 429);
    }
  }

  const report = await checkIdea(body.question, {
    claude: deps.claude || makeClaude(new Anthropic({ apiKey: env.ANTHROPIC_API_KEY })),
    fetch: deps.fetch || fetch,
    openAlexKey: env.OPENALEX_API_KEY,
  });
  if (kv) {
    const used = Number((await kv.get(counterKey)) || 0);
    await kv.put(counterKey, String(used + 1), { expirationTtl: 3 * 86_400 });
    await kv.put(cacheKey, JSON.stringify(report), { expirationTtl: CACHE_DAYS * 86_400 });
  }
  return json(report);
}

async function handleAccount(request, env, url, deps) {
  const kv = env.DATA;
  if (!kv) return json({ error: "Accounts aren't set up on this server yet." }, 503);
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  const path = url.pathname;
  const body = request.method === "GET" ? {} : await request.json().catch(() => ({}));
  const token = (request.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "");

  if (path.startsWith("/auth/")) {
    if ((deps.authLimited || authLimited)(ip)) return json({ error: "Too many attempts. Wait a few minutes and try again." }, 429);
    if (path === "/auth/signup" && request.method === "POST") return json(await signup(kv, body), 201);
    if (path === "/auth/login" && request.method === "POST") return json(await login(kv, body));
    if (path === "/auth/reset" && request.method === "POST") return json(await resetPassword(kv, body));
  }
  if (path === "/me" && request.method === "GET") return json(await getMe(kv, token));
  if (path === "/me/data" && request.method === "PUT") return json(await putData(kv, token, body.data));
  if (path === "/me/delete" && request.method === "POST") return json(await deleteAccount(kv, token, body.password));
  return json({ error: "Not found" }, 404);
}

export async function handle(request, env, deps = {}) {
  const url = new URL(request.url);
  if (request.method === "OPTIONS") return new Response(null, { headers: CORS });
  if (url.pathname === "/health") {
    return json({ ok: true, ai: Boolean(env.ANTHROPIC_API_KEY), openalex_key: Boolean(env.OPENALEX_API_KEY),
                  accounts: Boolean(env.DATA) });
  }
  try {
    if (url.pathname === "/check" && request.method === "POST") return await handleCheck(request, env, deps);
    if (url.pathname.startsWith("/auth/") || url.pathname.startsWith("/me")) {
      return await handleAccount(request, env, url, deps);
    }
    return json({ error: "Not found" }, 404);
  } catch (err) {
    if (err instanceof IdeaError || err instanceof AccountError) return json({ error: err.message }, err.status);
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
