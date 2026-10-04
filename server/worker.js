// Neon Veins account server — Cloudflare Worker + D1 (binding DB).
// Accounts (email + username + password), sessions, friends, presence/invites and cloud saves.
// Passwords: PBKDF2-SHA256 with a per-user salt. Sessions: random bearer tokens, only their SHA-256 is stored.

const DAY = 86400000;
const SESSION_MS = 90 * DAY;            // sliding: refreshed on use
const ONLINE_MS = 75000;                // presence heartbeat window
const INVITE_MS = 10 * 60000;
const ITERS = 40000;                    // PBKDF2 rounds (Workers cap: 100k; kept modest for the free-plan CPU limit)
const MAX_SAVE = 900 * 1024;
const MAX_SLOTS = 6;

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, PUT, PATCH, DELETE, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  'Access-Control-Max-Age': '86400',
};
const json = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json', ...CORS } });
const fail = (status, error, field) => json({ error, field }, status);
class HttpError extends Error { constructor(status, msg, field) { super(msg); this.status = status; this.field = field; } }
const bad = (msg, field) => { throw new HttpError(400, msg, field); };

const enc = new TextEncoder();
const hex = buf => [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('');
const randHex = n => hex(crypto.getRandomValues(new Uint8Array(n)));
const sha256 = async s => hex(await crypto.subtle.digest('SHA-256', enc.encode(s)));
async function pbkdf2(password, saltHex, iters) {
  const key = await crypto.subtle.importKey('raw', enc.encode(password), 'PBKDF2', false, ['deriveBits']);
  const salt = new Uint8Array(saltHex.match(/../g).map(h => parseInt(h, 16)));
  return hex(await crypto.subtle.deriveBits({ name: 'PBKDF2', hash: 'SHA-256', salt, iterations: iters }, key, 256));
}
function safeEq(a, b) { if (a.length !== b.length) return false; let r = 0; for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i); return r === 0; }

const EMAIL_RE = /^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,24}$/;
const USER_RE = /^[A-Za-z0-9_\-]{3,20}$/;
const COLOR_RE = /^#[0-9a-fA-F]{6}$/;
function checkPassword(p) {
  if (typeof p !== 'string' || p.length < 8) bad('Password must be at least 8 characters.', 'password');
  if (p.length > 200) bad('Password is too long.', 'password');
  if (!/[A-Za-z]/.test(p) || !/[0-9]/.test(p)) bad('Password needs at least one letter and one number.', 'password');
}
function checkEmail(e) { if (typeof e !== 'string' || !EMAIL_RE.test(e.trim()) || e.length > 254) bad('Enter a valid email address.', 'email'); return e.trim().toLowerCase(); }
function checkUsername(u) { if (typeof u !== 'string' || !USER_RE.test(u.trim())) bad('Usernames are 3–20 letters, numbers, _ or -.', 'username'); return u.trim(); }

// simple fixed-window rate limiting stored in D1
async function limit(env, key, max, windowMs) {
  const now = Date.now();
  const row = await env.DB.prepare('SELECT n, since FROM attempts WHERE k = ?').bind(key).first();
  if (!row || now - row.since > windowMs) { await env.DB.prepare('INSERT OR REPLACE INTO attempts (k, n, since) VALUES (?, 1, ?)').bind(key, now).run(); return; }
  if (row.n >= max) throw new HttpError(429, 'Too many attempts. Try again in a few minutes.');
  await env.DB.prepare('UPDATE attempts SET n = n + 1 WHERE k = ?').bind(key).run();
}

const publicUser = u => ({ id: u.id, username: u.username, color: u.color, bio: u.bio, created: u.created });
const privateUser = u => ({ ...publicUser(u), email: u.email, allow_requests: !!u.allow_requests, show_online: !!u.show_online });

async function newSession(env, userId, device) {
  const token = randHex(32), now = Date.now();
  await env.DB.prepare('INSERT INTO sessions (token_hash, user_id, created, expires, device) VALUES (?, ?, ?, ?, ?)').bind(await sha256(token), userId, now, now + SESSION_MS, String(device || '').slice(0, 80)).run();
  return token;
}
async function auth(req, env) {
  const h = req.headers.get('Authorization') || '';
  const token = h.startsWith('Bearer ') ? h.slice(7).trim() : '';
  if (!/^[0-9a-f]{64}$/.test(token)) throw new HttpError(401, 'Please sign in.');
  const th = await sha256(token), now = Date.now();
  const s = await env.DB.prepare('SELECT user_id, expires FROM sessions WHERE token_hash = ?').bind(th).first();
  if (!s || s.expires < now) throw new HttpError(401, 'Your session expired. Please sign in again.');
  const u = await env.DB.prepare('SELECT * FROM users WHERE id = ?').bind(s.user_id).first();
  if (!u) throw new HttpError(401, 'Account not found.');
  if (s.expires - now < SESSION_MS - DAY) await env.DB.prepare('UPDATE sessions SET expires = ? WHERE token_hash = ?').bind(now + SESSION_MS, th).run();
  return { user: u, th };
}
async function verifyPassword(u, password) {
  if (typeof password !== 'string') return false;
  return safeEq(await pbkdf2(password, u.salt, u.iters), u.pass_hash);
}
const pair = (x, y) => (x < y ? [x, y] : [y, x]);
const online = (u, now) => !!u.show_online && now - u.last_seen < ONLINE_MS;

async function body(req) { try { const b = await req.json(); return b && typeof b === 'object' ? b : {}; } catch (e) { return {}; } }

const routes = [];
const route = (method, pattern, fn) => routes.push({ method, re: new RegExp('^' + pattern.replace(/:(\w+)/g, '(?<$1>[^/]+)') + '$'), fn });

/* ---------------- accounts ---------------- */
route('POST', '/api/signup', async (req, env) => {
  const b = await body(req), ip = req.headers.get('CF-Connecting-IP') || 'x';
  const email = checkEmail(b.email), username = checkUsername(b.username); checkPassword(b.password);
  await limit(env, 'signup:' + ip, 6, 3600000);
  if (await env.DB.prepare('SELECT 1 FROM users WHERE email = ?').bind(email).first()) bad('That email already has an account.', 'email');
  if (await env.DB.prepare('SELECT 1 FROM users WHERE username = ?').bind(username).first()) bad('That username is taken.', 'username');
  const salt = randHex(16), hash = await pbkdf2(b.password, salt, ITERS), now = Date.now();
  const color = COLOR_RE.test(b.color || '') ? b.color : '#19f0ff';
  const r = await env.DB.prepare('INSERT INTO users (email, username, pass_hash, salt, iters, color, created, last_seen) VALUES (?, ?, ?, ?, ?, ?, ?, ?)').bind(email, username, hash, salt, ITERS, color, now, now).run();
  const u = await env.DB.prepare('SELECT * FROM users WHERE id = ?').bind(r.meta.last_row_id).first();
  return json({ token: await newSession(env, u.id, b.device), user: privateUser(u) });
});

route('POST', '/api/login', async (req, env) => {
  const b = await body(req), ip = req.headers.get('CF-Connecting-IP') || 'x', login = String(b.login || '').trim();
  if (!login) bad('Enter your email or username.', 'login');
  await limit(env, 'login-ip:' + ip, 20, 900000);
  await limit(env, 'login:' + login.toLowerCase(), 8, 900000);
  const u = await env.DB.prepare('SELECT * FROM users WHERE email = ? OR username = ?').bind(login.toLowerCase(), login).first();
  if (!u || !(await verifyPassword(u, b.password))) throw new HttpError(401, 'Wrong email/username or password.');
  await env.DB.prepare('DELETE FROM attempts WHERE k = ?').bind('login:' + login.toLowerCase()).run();
  await env.DB.prepare('DELETE FROM sessions WHERE user_id = ? AND expires < ?').bind(u.id, Date.now()).run();
  return json({ token: await newSession(env, u.id, b.device), user: privateUser(u) });
});

route('POST', '/api/logout', async (req, env) => { const { th } = await auth(req, env); await env.DB.prepare('DELETE FROM sessions WHERE token_hash = ?').bind(th).run(); return json({ ok: true }); });
route('POST', '/api/logout-all', async (req, env) => { const { user } = await auth(req, env); await env.DB.prepare('DELETE FROM sessions WHERE user_id = ?').bind(user.id).run(); return json({ ok: true }); });

route('GET', '/api/me', async (req, env) => {
  const { user } = await auth(req, env);
  const sessions = await env.DB.prepare('SELECT created, expires, device FROM sessions WHERE user_id = ? ORDER BY created DESC LIMIT 20').bind(user.id).all();
  return json({ user: privateUser(user), sessions: sessions.results });
});

route('PATCH', '/api/me', async (req, env) => {
  const { user } = await auth(req, env), b = await body(req), set = {};
  if (b.username != null && b.username !== user.username) {
    const n = checkUsername(b.username);
    if (n.toLowerCase() !== user.username.toLowerCase() && await env.DB.prepare('SELECT 1 FROM users WHERE username = ?').bind(n).first()) bad('That username is taken.', 'username');
    set.username = n;
  }
  if (b.email != null && b.email.toLowerCase() !== user.email) {
    if (!(await verifyPassword(user, b.password))) bad('Enter your current password to change your email.', 'password');
    const e = checkEmail(b.email);
    if (await env.DB.prepare('SELECT 1 FROM users WHERE email = ?').bind(e).first()) bad('That email already has an account.', 'email');
    set.email = e;
  }
  if (b.color != null) { if (!COLOR_RE.test(b.color)) bad('Pick a colour.', 'color'); set.color = b.color; }
  if (b.bio != null) set.bio = String(b.bio).replace(/[\u0000-\u001f]/g, ' ').slice(0, 140);
  if (b.allow_requests != null) set.allow_requests = b.allow_requests ? 1 : 0;
  if (b.show_online != null) set.show_online = b.show_online ? 1 : 0;
  const keys = Object.keys(set);
  if (keys.length) await env.DB.prepare('UPDATE users SET ' + keys.map(k => k + ' = ?').join(', ') + ' WHERE id = ?').bind(...keys.map(k => set[k]), user.id).run();
  const u = await env.DB.prepare('SELECT * FROM users WHERE id = ?').bind(user.id).first();
  return json({ user: privateUser(u) });
});

route('POST', '/api/me/password', async (req, env) => {
  const { user, th } = await auth(req, env), b = await body(req);
  await limit(env, 'pw:' + user.id, 8, 900000);
  if (!(await verifyPassword(user, b.current))) bad('Your current password is wrong.', 'current');
  checkPassword(b.next);
  const salt = randHex(16);
  await env.DB.prepare('UPDATE users SET pass_hash = ?, salt = ?, iters = ? WHERE id = ?').bind(await pbkdf2(b.next, salt, ITERS), salt, ITERS, user.id).run();
  await env.DB.prepare('DELETE FROM sessions WHERE user_id = ? AND token_hash != ?').bind(user.id, th).run(); // sign out every other device
  return json({ ok: true });
});

route('DELETE', '/api/me', async (req, env) => {
  const { user } = await auth(req, env), b = await body(req);
  if (!(await verifyPassword(user, b.password))) bad('Enter your password to delete your account.', 'password');
  const id = user.id;
  await env.DB.batch([
    env.DB.prepare('DELETE FROM saves WHERE user_id = ?').bind(id),
    env.DB.prepare('DELETE FROM friends WHERE a = ? OR b = ?').bind(id, id),
    env.DB.prepare('DELETE FROM invites WHERE from_id = ? OR to_id = ?').bind(id, id),
    env.DB.prepare('DELETE FROM sessions WHERE user_id = ?').bind(id),
    env.DB.prepare('DELETE FROM users WHERE id = ?').bind(id),
  ]);
  return json({ ok: true });
});

/* ---------------- presence & invites ---------------- */
route('POST', '/api/presence', async (req, env) => {
  const { user } = await auth(req, env), b = await body(req), now = Date.now();
  const code = /^[A-Z0-9]{6}$/.test(b.join_code || '') ? b.join_code : '';
  await env.DB.prepare('UPDATE users SET last_seen = ?, activity = ?, join_code = ? WHERE id = ?').bind(now, String(b.activity || '').slice(0, 60), code, user.id).run();
  const inv = await env.DB.prepare('SELECT i.id, i.code, i.created, u.username, u.color FROM invites i JOIN users u ON u.id = i.from_id WHERE i.to_id = ? AND i.created > ? ORDER BY i.created DESC LIMIT 5').bind(user.id, now - INVITE_MS).all();
  const req2 = await env.DB.prepare("SELECT COUNT(*) AS n FROM friends WHERE (a = ? OR b = ?) AND state = 'pending' AND requester != ?").bind(user.id, user.id, user.id).first();
  await env.DB.prepare('DELETE FROM invites WHERE created < ?').bind(now - INVITE_MS).run();
  return json({ invites: inv.results, requests: req2 ? req2.n : 0 });
});

route('POST', '/api/invites', async (req, env) => {
  const { user } = await auth(req, env), b = await body(req);
  if (!/^[A-Z0-9]{6}$/.test(b.code || '')) bad('Host a game first.');
  const to = Number(b.to), [a, c] = pair(user.id, to);
  const f = await env.DB.prepare("SELECT state FROM friends WHERE a = ? AND b = ?").bind(a, c).first();
  if (!f || f.state !== 'accepted') bad('You can only invite friends.');
  await limit(env, 'inv:' + user.id, 30, 600000);
  await env.DB.prepare('INSERT INTO invites (from_id, to_id, code, created) VALUES (?, ?, ?, ?)').bind(user.id, to, b.code, Date.now()).run();
  return json({ ok: true });
});

/* ---------------- friends ---------------- */
route('GET', '/api/friends', async (req, env) => {
  const { user } = await auth(req, env), now = Date.now();
  const rows = await env.DB.prepare('SELECT f.state, f.requester, f.created AS since, u.* FROM friends f JOIN users u ON u.id = (CASE WHEN f.a = ? THEN f.b ELSE f.a END) WHERE f.a = ? OR f.b = ? ORDER BY u.username COLLATE NOCASE').bind(user.id, user.id, user.id).all();
  const friends = [], incoming = [], outgoing = [];
  for (const r of rows.results) {
    const p = { ...publicUser(r), since: r.since };
    if (r.state === 'accepted') { const on = online(r, now); friends.push({ ...p, online: on, activity: on ? r.activity : '', join_code: on ? r.join_code : '', last_seen: r.show_online ? r.last_seen : 0 }); }
    else if (r.requester === user.id) outgoing.push(p); else incoming.push(p);
  }
  friends.sort((x, y) => (y.online - x.online) || x.username.localeCompare(y.username));
  return json({ friends, incoming, outgoing });
});

route('GET', '/api/users/search', async (req, env) => {
  const { user } = await auth(req, env), q = new URL(req.url).searchParams.get('q') || '';
  if (q.trim().length < 2) return json({ users: [] });
  const like = q.trim().replace(/[%_\\]/g, '\\$&') + '%';
  const rows = await env.DB.prepare("SELECT * FROM users WHERE username LIKE ? ESCAPE '\\' AND id != ? ORDER BY length(username) LIMIT 10").bind(like, user.id).all();
  return json({ users: rows.results.map(publicUser) });
});

route('GET', '/api/users/:name', async (req, env, p) => {
  const { user } = await auth(req, env);
  const u = await env.DB.prepare('SELECT * FROM users WHERE username = ?').bind(decodeURIComponent(p.name)).first();
  if (!u) throw new HttpError(404, 'No player with that username.');
  const [a, b] = pair(user.id, u.id), f = await env.DB.prepare('SELECT state, requester FROM friends WHERE a = ? AND b = ?').bind(a, b).first();
  return json({ user: publicUser(u), relation: !f ? 'none' : f.state === 'accepted' ? 'friend' : f.requester === user.id ? 'outgoing' : 'incoming' });
});

route('POST', '/api/friends/request', async (req, env) => {
  const { user } = await auth(req, env), b = await body(req);
  await limit(env, 'fr:' + user.id, 40, 3600000);
  const t = await env.DB.prepare('SELECT * FROM users WHERE username = ?').bind(String(b.username || '').trim()).first();
  if (!t) bad('No player with that username.', 'username');
  if (t.id === user.id) bad("That's you.", 'username');
  const [a, c] = pair(user.id, t.id), f = await env.DB.prepare('SELECT state, requester FROM friends WHERE a = ? AND b = ?').bind(a, c).first();
  if (f && f.state === 'accepted') bad("You're already friends.", 'username');
  if (f && f.requester === user.id) bad('Request already sent.', 'username');
  if (f) { await env.DB.prepare("UPDATE friends SET state = 'accepted' WHERE a = ? AND b = ?").bind(a, c).run(); return json({ ok: true, accepted: true }); } // they had asked you: accept
  if (!t.allow_requests) bad('That player is not accepting friend requests.', 'username');
  await env.DB.prepare("INSERT INTO friends (a, b, state, requester, created) VALUES (?, ?, 'pending', ?, ?)").bind(a, c, user.id, Date.now()).run();
  return json({ ok: true });
});

route('POST', '/api/friends/respond', async (req, env) => {
  const { user } = await auth(req, env), b = await body(req), [a, c] = pair(user.id, Number(b.id));
  const f = await env.DB.prepare('SELECT * FROM friends WHERE a = ? AND b = ?').bind(a, c).first();
  if (!f || f.state !== 'pending' || f.requester === user.id) bad('No request to answer.');
  if (b.accept) await env.DB.prepare("UPDATE friends SET state = 'accepted', created = ? WHERE a = ? AND b = ?").bind(Date.now(), a, c).run();
  else await env.DB.prepare('DELETE FROM friends WHERE a = ? AND b = ?').bind(a, c).run();
  return json({ ok: true });
});

route('DELETE', '/api/friends/:id', async (req, env, p) => {
  const { user } = await auth(req, env), [a, c] = pair(user.id, Number(p.id));
  await env.DB.prepare('DELETE FROM friends WHERE a = ? AND b = ?').bind(a, c).run();
  return json({ ok: true });
});

/* ---------------- cloud saves ---------------- */
const SLOT_RE = /^[a-z0-9_\-]{1,16}$/;
route('GET', '/api/saves', async (req, env) => {
  const { user } = await auth(req, env);
  const rows = await env.DB.prepare('SELECT slot, summary, updated, length(data) AS size FROM saves WHERE user_id = ? ORDER BY updated DESC').bind(user.id).all();
  return json({ saves: rows.results });
});
route('GET', '/api/saves/:slot', async (req, env, p) => {
  const { user } = await auth(req, env);
  const r = await env.DB.prepare('SELECT slot, data, summary, updated FROM saves WHERE user_id = ? AND slot = ?').bind(user.id, p.slot).first();
  if (!r) throw new HttpError(404, 'No cloud save in that slot.');
  return json(r);
});
route('PUT', '/api/saves/:slot', async (req, env, p) => {
  const { user } = await auth(req, env), b = await body(req);
  if (!SLOT_RE.test(p.slot)) bad('Bad slot name.');
  if (typeof b.data !== 'string' || !b.data) bad('Nothing to save.');
  if (b.data.length > MAX_SAVE) throw new HttpError(413, 'Save is too large for the cloud.');
  await limit(env, 'save:' + user.id, 120, 3600000);
  const n = await env.DB.prepare('SELECT COUNT(*) AS n FROM saves WHERE user_id = ? AND slot != ?').bind(user.id, p.slot).first();
  if (n && n.n >= MAX_SLOTS) bad('Cloud save slots are full.');
  const updated = Number(b.updated) || Date.now();
  await env.DB.prepare('INSERT OR REPLACE INTO saves (user_id, slot, data, summary, updated) VALUES (?, ?, ?, ?, ?)').bind(user.id, p.slot, b.data, String(b.summary || '').slice(0, 200), updated).run();
  return json({ ok: true, updated });
});
route('DELETE', '/api/saves/:slot', async (req, env, p) => {
  const { user } = await auth(req, env);
  await env.DB.prepare('DELETE FROM saves WHERE user_id = ? AND slot = ?').bind(user.id, p.slot).run();
  return json({ ok: true });
});

route('GET', '/api/health', async () => json({ ok: true, service: 'neon-veins-api' }));

export default {
  async fetch(req, env) {
    if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: CORS });
    const path = new URL(req.url).pathname.replace(/\/+$/, '') || '/';
    if (path === '/') return json({ ok: true, service: 'neon-veins-api' });
    for (const r of routes) {
      if (r.method !== req.method) continue;
      const m = path.match(r.re);
      if (!m) continue;
      try { return await r.fn(req, env, m.groups || {}); }
      catch (e) {
        if (e instanceof HttpError) return fail(e.status, e.message, e.field);
        console.error(e); return fail(500, 'Server error. Please try again.');
      }
    }
    return fail(404, 'Not found.');
  },
};
