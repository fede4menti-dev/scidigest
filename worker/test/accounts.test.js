// Accounts, idea-check cache and daily cap, with an in-memory stand-in for Cloudflare KV.
import { test } from "node:test";
import assert from "node:assert/strict";
import { handle } from "../src/index.js";
import { readToken } from "../src/accounts.js";

function memoryKV() {
  const m = new Map();
  return {
    m,
    async get(k, type) { const v = m.get(k); return v === undefined ? null : type === "json" ? JSON.parse(v) : v; },
    async put(k, v) { m.set(k, v); },
    async delete(k) { m.delete(k); },
  };
}

const call = (env, method, path, body, token, deps = {}) => handle(new Request("https://w.dev" + path, {
  method, body: body === undefined ? undefined : JSON.stringify(body),
  headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
}), env, { authLimited: () => false, rateLimited: () => false, ...deps });

test("sign up, sync data, sign in elsewhere, recover password, delete", async () => {
  const kv = memoryKV(), env = { DATA: kv };
  let r = await call(env, "POST", "/auth/signup", { email: " Student@Uni.edu ", password: "correct horse", data: { topics: ["physics"] } });
  assert.equal(r.status, 201);
  const s = await r.json();
  assert.match(s.recovery_code, /^[A-Z2-9]{4}(-[A-Z2-9]{4}){3}$/);
  assert.equal(s.account.email, "student@uni.edu");
  const stored = JSON.parse(kv.m.get("user:student@uni.edu"));
  assert.ok(!JSON.stringify(stored).includes("correct horse"), "password never stored");
  assert.ok(!JSON.stringify(stored).includes(s.recovery_code.replace(/-/g, "")), "recovery code never stored");

  assert.equal((await call(env, "POST", "/auth/signup", { email: "student@uni.edu", password: "another pw" })).status, 409);
  assert.equal((await call(env, "POST", "/auth/signup", { email: "nope", password: "12345678" })).status, 400);
  assert.equal((await call(env, "POST", "/auth/signup", { email: "a@b.co", password: "short" })).status, 400);

  r = await call(env, "PUT", "/me/data", { data: { topics: ["physics", "chemistry"], saved: { x: 1 } } }, s.token);
  assert.equal(r.status, 200);
  assert.equal((await call(env, "PUT", "/me/data", { data: { big: "x".repeat(200_000) } }, s.token)).status, 413);

  assert.equal((await call(env, "POST", "/auth/login", { email: "student@uni.edu", password: "wrong pass" })).status, 401);
  r = await call(env, "POST", "/auth/login", { email: "STUDENT@uni.edu", password: "correct horse" });
  const l = await r.json();
  assert.equal(r.status, 200);
  const me = await (await call(env, "GET", "/me", undefined, l.token)).json();
  assert.deepEqual(me.data.topics, ["physics", "chemistry"]);

  assert.equal((await call(env, "GET", "/me", undefined, "garbage.token")).status, 401);
  assert.equal((await call(env, "GET", "/me", undefined, l.token.slice(0, -2) + "xx")).status, 401, "tampered token");

  assert.equal((await call(env, "POST", "/auth/reset", { email: "student@uni.edu", recovery_code: "AAAA-BBBB-CCCC-DDDD", new_password: "new password" })).status, 401);
  r = await call(env, "POST", "/auth/reset", { email: "student@uni.edu", recovery_code: s.recovery_code.toLowerCase(), new_password: "new password" });
  assert.equal(r.status, 200);
  const reset = await r.json();
  assert.notEqual(reset.recovery_code, s.recovery_code, "a new recovery code is issued");
  assert.equal((await call(env, "POST", "/auth/login", { email: "student@uni.edu", password: "correct horse" })).status, 401);
  assert.equal((await call(env, "POST", "/auth/login", { email: "student@uni.edu", password: "new password" })).status, 200);

  assert.equal((await call(env, "POST", "/me/delete", { password: "wrong" }, reset.token)).status, 401);
  assert.equal((await call(env, "POST", "/me/delete", { password: "new password" }, reset.token)).status, 200);
  assert.equal(kv.m.has("user:student@uni.edu"), false);
  assert.equal((await call(env, "GET", "/me", undefined, reset.token)).status, 401);
});

test("tokens expire", async () => {
  const kv = memoryKV();
  const s = await (await call({ DATA: kv }, "POST", "/auth/signup", { email: "e@x.io", password: "12345678" })).json();
  await assert.rejects(readToken(kv, s.token, Date.now() + 91 * 86_400_000), /expired/);
});

test("accounts need storage; sign-in attempts are rate limited", async () => {
  assert.equal((await call({}, "POST", "/auth/login", { email: "a@b.co", password: "x" })).status, 503);
  const r = await call({ DATA: memoryKV() }, "POST", "/auth/login", {}, undefined, { authLimited: () => true });
  assert.equal(r.status, 429);
});

test("idea checks: cached repeats cost nothing; daily cap", async () => {
  const kv = memoryKV();
  let claudeCalls = 0;
  const claude = async (sys, prompt, schema) => {
    claudeCalls++;
    if (schema.properties.queries) return { is_research_question: true, field: "Biology", queries: ["q one"] };
    const scored = { score: 5, comment: "ok" };
    return { verdict: "partly researched", novelty_score: 5, overall_score: 5, summary: "s", related: [],
             quality: { clarity: scored, specificity: scored, feasibility: scored, significance: scored, testability: scored },
             ethics: "none", gaps: [], suggestions: [], improved_question: "q" };
  };
  const fetch = async () => ({ ok: true, status: 200, json: async () => ({ results: [{ display_name: "Paper", id: "W1", cited_by_count: 1 }] }) });
  const env = { DATA: kv, ANTHROPIC_API_KEY: "k", DAILY_CHECK_LIMIT: "2" };
  const ask = (q) => call(env, "POST", "/check", { question: q }, undefined, { claude, fetch });

  let r = await ask("Does sleep improve memory in students?");
  assert.equal(r.status, 200);
  assert.equal(claudeCalls, 2);
  r = await ask("does SLEEP improve memory in students");          // same question, different case/punctuation
  assert.equal((await r.json()).cached, true);
  assert.equal(claudeCalls, 2, "no new AI calls for a cached question");
  assert.equal(r.status, 200);

  assert.equal((await ask("Do bees prefer blue flowers over yellow ones?")).status, 200);
  r = await ask("Can soil microbes break down plastic quickly?");     // third new question, limit is 2
  assert.equal(r.status, 429);
  assert.match((await r.json()).error, /today's limit/);
  assert.equal(claudeCalls, 4);
});
