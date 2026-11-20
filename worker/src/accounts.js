// Accounts that sync a reader's preferences and data across devices.
//
// Storage: Cloudflare KV (binding DATA).
//   user:<email>      {id, email, salt, hash, recoveryHash, created, updated, data}
//   config:session    random secret used to sign session tokens (created on first use)
// Passwords and recovery codes are stored only as PBKDF2-SHA256 hashes.
// There is no email service, so a forgotten password is reset with the recovery code
// shown once at sign-up.

const ITERATIONS = 100_000;              // Cloudflare Workers' PBKDF2 maximum
const SESSION_DAYS = 90;
export const MAX_DATA_BYTES = 128 * 1024;

export class AccountError extends Error {
  constructor(message, status = 400) {
    super(message);
    this.status = status;
  }
}

const enc = new TextEncoder();
const b64url = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf)))
  .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const fromB64url = (s) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
const randomBytes = (n) => crypto.getRandomValues(new Uint8Array(n));

async function pbkdf2(secret, salt) {
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits({ name: "PBKDF2", hash: "SHA-256", salt, iterations: ITERATIONS }, key, 256);
  return b64url(bits);
}

function sameString(a, b) {           // constant-time comparison
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function recoveryCode() {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";   // no 0/O/1/I
  const bytes = randomBytes(16);
  const chars = [...bytes].map((b) => alphabet[b % alphabet.length]).join("");
  return chars.match(/.{4}/g).join("-");
}

const normEmail = (e) => String(e || "").trim().toLowerCase();

function checkEmail(email) {
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email) || email.length > 254) {
    throw new AccountError("Please enter a valid email address.");
  }
}

function checkPassword(pw) {
  if (typeof pw !== "string" || pw.length < 8) throw new AccountError("Use a password with at least 8 characters.");
  if (pw.length > 200) throw new AccountError("That password is too long.");
}

// ------------------------------------------------------------------ sessions

async function sessionKey(kv) {
  let secret = await kv.get("config:session");
  if (!secret) {
    secret = b64url(randomBytes(32));
    await kv.put("config:session", secret);
  }
  return crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]);
}

export async function makeToken(kv, user, now = Date.now()) {
  const body = b64url(enc.encode(JSON.stringify({ sub: user.id, email: user.email, exp: now + SESSION_DAYS * 86_400_000 })));
  const sig = await crypto.subtle.sign("HMAC", await sessionKey(kv), enc.encode(body));
  return `${body}.${b64url(sig)}`;
}

export async function readToken(kv, token, now = Date.now()) {
  const again = new AccountError("Please sign in again.", 401);
  const [body, sig] = String(token || "").split(".");
  if (!body || !sig) throw again;
  let claims;
  try {
    const ok = await crypto.subtle.verify("HMAC", await sessionKey(kv), fromB64url(sig), enc.encode(body));
    if (!ok) throw again;
    claims = JSON.parse(new TextDecoder().decode(fromB64url(body)));
  } catch {
    throw again;   // malformed or tampered token
  }
  if (claims.exp < now) throw new AccountError("Your session expired. Please sign in again.", 401);
  return claims;
}

// ------------------------------------------------------------------ users

const userKey = (email) => `user:${email}`;

async function loadUser(kv, email) {
  return kv.get(userKey(email), "json");
}

async function saveUser(kv, user) {
  await kv.put(userKey(user.email), JSON.stringify(user));
}

const publicView = (u) => ({ email: u.email, created: u.created, updated: u.updated, data: u.data || {} });

export async function signup(kv, { email, password, data }) {
  email = normEmail(email);
  checkEmail(email);
  checkPassword(password);
  if (await loadUser(kv, email)) throw new AccountError("An account with this email already exists. Sign in instead.", 409);
  const salt = randomBytes(16);
  const code = recoveryCode();
  const now = new Date().toISOString();
  const user = {
    id: b64url(randomBytes(12)), email, salt: b64url(salt),
    hash: await pbkdf2(password, salt),
    recoveryHash: await pbkdf2(code.replace(/-/g, ""), salt),
    created: now, updated: now, data: limitData(data || {}),
  };
  await saveUser(kv, user);
  return { token: await makeToken(kv, user), recovery_code: code, account: publicView(user) };
}

export async function login(kv, { email, password }) {
  email = normEmail(email);
  const user = await loadUser(kv, email);
  const wrong = new AccountError("Wrong email or password.", 401);
  if (!user) throw wrong;
  const hash = await pbkdf2(String(password || ""), fromB64url(user.salt));
  if (!sameString(hash, user.hash)) throw wrong;
  return { token: await makeToken(kv, user), account: publicView(user) };
}

export async function resetPassword(kv, { email, recovery_code, new_password }) {
  email = normEmail(email);
  checkPassword(new_password);
  const user = await loadUser(kv, email);
  const wrong = new AccountError("That email and recovery code don't match.", 401);
  if (!user) throw wrong;
  const salt = fromB64url(user.salt);
  const given = await pbkdf2(String(recovery_code || "").toUpperCase().replace(/[^A-Z0-9]/g, ""), salt);
  if (!sameString(given, user.recoveryHash)) throw wrong;
  const newSalt = randomBytes(16);
  const code = recoveryCode();
  user.salt = b64url(newSalt);
  user.hash = await pbkdf2(new_password, newSalt);
  user.recoveryHash = await pbkdf2(code.replace(/-/g, ""), newSalt);
  user.updated = new Date().toISOString();
  await saveUser(kv, user);
  return { token: await makeToken(kv, user), recovery_code: code, account: publicView(user) };
}

async function userFromToken(kv, token) {
  const claims = await readToken(kv, token);
  const user = await loadUser(kv, claims.email);
  if (!user || user.id !== claims.sub) throw new AccountError("This account no longer exists.", 401);
  return user;
}

export async function getMe(kv, token) {
  return publicView(await userFromToken(kv, token));
}

function limitData(data) {
  if (typeof data !== "object" || data === null || Array.isArray(data)) throw new AccountError("Data must be an object.");
  if (enc.encode(JSON.stringify(data)).length > MAX_DATA_BYTES) {
    throw new AccountError("Too much data to sync. Remove some saved papers or idea checks.", 413);
  }
  return data;
}

export async function putData(kv, token, data) {
  const user = await userFromToken(kv, token);
  user.data = limitData(data);
  user.updated = new Date().toISOString();
  await saveUser(kv, user);
  return { updated: user.updated };
}

export async function deleteAccount(kv, token, password) {
  const user = await userFromToken(kv, token);
  const hash = await pbkdf2(String(password || ""), fromB64url(user.salt));
  if (!sameString(hash, user.hash)) throw new AccountError("Wrong password.", 401);
  await kv.delete(userKey(user.email));
  return { deleted: true };
}
