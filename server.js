'use strict';
/*
 * Máy chủ Hệ thống TKB — Trường THCS-THPT Nguyễn Khuyến
 * - Mọi người xem công khai (GET /api/data)
 * - Quản trị đăng nhập bằng mã PIN, bấm "Công bố" để lưu TKB mới (POST /api/data)
 * - Lưu dữ liệu: GitHub (bền vững, khuyên dùng) hoặc tệp cục bộ (chỉ để thử, mất khi Render khởi động lại)
 * Không phụ thuộc thư viện ngoài.
 */
const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const PORT = parseInt(process.env.PORT || '3000', 10);
const ADMIN_PIN = process.env.ADMIN_PIN || '';
const SESSION_SECRET = process.env.SESSION_SECRET || crypto.randomBytes(32).toString('hex');
const GITHUB_TOKEN = process.env.GITHUB_TOKEN || '';
const GITHUB_REPO = process.env.GITHUB_REPO || '';          // dạng owner/repo
const GITHUB_FILE = process.env.GITHUB_FILE || 'dulieu.json';
const GITHUB_BRANCH = process.env.GITHUB_BRANCH || 'render';
const DATA_DIR = process.env.DATA_DIR || path.join(__dirname, 'data');
const SEED_FILE = path.join(__dirname, 'seed', 'dulieu.json');
const SESSION_MS = 8 * 60 * 60 * 1000;
const MAX_BODY = 8 * 1024 * 1024;
const STORAGE = (GITHUB_TOKEN && GITHUB_REPO) ? 'github' : 'file';

if (!ADMIN_PIN) console.warn('[CẢNH BÁO] Chưa đặt ADMIN_PIN — không ai đăng nhập quản trị được.');
if (STORAGE === 'file') console.warn('[CẢNH BÁO] Đang lưu dữ liệu bằng tệp cục bộ: sẽ MẤT khi Render khởi động lại. Hãy đặt GITHUB_TOKEN + GITHUB_REPO.');

/* ---------- tiện ích ---------- */
const sha1 = (s) => crypto.createHash('sha1').update(s).digest('hex');
function safeEqual(a, b) {
  const ba = Buffer.from(String(a)); const bb = Buffer.from(String(b));
  const len = Math.max(ba.length, bb.length, 1);
  const pa = Buffer.alloc(len); const pb = Buffer.alloc(len);
  ba.copy(pa); bb.copy(pb);
  return crypto.timingSafeEqual(pa, pb) && ba.length === bb.length;
}
function sign(payload) {
  return crypto.createHmac('sha256', SESSION_SECRET).update(payload).digest('base64url');
}
function makeToken() {
  const exp = Date.now() + SESSION_MS;
  const p = 'admin.' + exp;
  return p + '.' + sign(p);
}
function checkToken(tok) {
  if (!tok) return false;
  const parts = tok.split('.');
  if (parts.length !== 3 || parts[0] !== 'admin') return false;
  const p = parts[0] + '.' + parts[1];
  if (!safeEqual(sign(p), parts[2])) return false;
  return Number(parts[1]) > Date.now();
}
function parseCookies(req) {
  const out = {};
  (req.headers.cookie || '').split(';').forEach((c) => {
    const i = c.indexOf('=');
    if (i > 0) out[c.slice(0, i).trim()] = decodeURIComponent(c.slice(i + 1).trim());
  });
  return out;
}
function isAdmin(req) { return checkToken(parseCookies(req).tkb_admin); }
function clientIp(req) {
  return (req.headers['x-forwarded-for'] || req.socket.remoteAddress || '').split(',')[0].trim();
}
function isHttps(req) { return (req.headers['x-forwarded-proto'] || '') === 'https'; }
function send(res, code, obj, extra) {
  const body = JSON.stringify(obj);
  res.writeHead(code, Object.assign({
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
  }, extra || {}));
  res.end(body);
}
function readBody(req) {
  return new Promise((resolve, reject) => {
    let size = 0; const chunks = [];
    req.on('data', (c) => {
      size += c.length;
      if (size > MAX_BODY) { reject(Object.assign(new Error('too large'), { status: 413 })); req.destroy(); return; }
      chunks.push(c);
    });
    req.on('end', () => {
      try { resolve(JSON.parse(Buffer.concat(chunks).toString('utf8') || '{}')); }
      catch (e) { reject(Object.assign(new Error('bad json'), { status: 400 })); }
    });
    req.on('error', reject);
  });
}
function originOk(req) {
  const origin = req.headers.origin;
  if (!origin) return true; // cùng nguồn gốc (một số trình duyệt không gửi Origin với POST cùng site)
  try { return new URL(origin).host === req.headers.host; } catch (e) { return false; }
}

/* ---------- giới hạn đăng nhập sai ---------- */
const fails = new Map(); // ip -> {n, until}
function lockedOut(ip) {
  const f = fails.get(ip);
  if (!f) return 0;
  if (f.until && f.until > Date.now()) return f.until - Date.now();
  if (f.until && f.until <= Date.now()) fails.delete(ip);
  return 0;
}
function recordFail(ip) {
  const f = fails.get(ip) || { n: 0, until: 0 };
  f.n += 1;
  if (f.n >= 5) { f.until = Date.now() + 15 * 60 * 1000; f.n = 0; }
  fails.set(ip, f);
}

/* ---------- kho dữ liệu ---------- */
function normalize(d) {
  const store = (d && typeof d.store === 'object' && d.store && !Array.isArray(d.store)) ? d.store : {};
  const namHocOptions = Array.isArray(d && d.namHocOptions) ? d.namHocOptions.filter((x) => typeof x === 'string').slice(0, 50) : [];
  const out = { store, namHocOptions, syncedAt: (d && d.syncedAt) || null };
  if (d && typeof d.namHoc === 'string' && d.namHoc.length < 20) out.namHoc = d.namHoc;
  if (d && typeof d.hocKy === 'string' && d.hocKy.length < 40) out.hocKy = d.hocKy;
  return out;
}
function hasRealData(store) {
  return Object.values(store || {}).some((c) => c && ((c.roster && c.roster.length > 0) || (c.classes && c.classes.length > 0)));
}

const fileStore = {
  file() { return path.join(DATA_DIR, 'dulieu.json'); },
  async read() {
    for (const f of [this.file(), SEED_FILE]) {
      try {
        const txt = fs.readFileSync(f, 'utf8');
        const d = normalize(JSON.parse(txt));
        return { data: d, rev: sha1(txt) };
      } catch (e) { /* thử tiếp */ }
    }
    return { data: normalize({}), rev: 'empty' };
  },
  async write(data) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
    const txt = JSON.stringify(data);
    const tmp = this.file() + '.tmp';
    fs.writeFileSync(tmp, txt);
    fs.renameSync(tmp, this.file());
    return { rev: sha1(txt) };
  },
};

const ghStore = {
  headers(raw) {
    return {
      Authorization: 'Bearer ' + GITHUB_TOKEN,
      Accept: raw ? 'application/vnd.github.raw+json' : 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'tkb-render',
    };
  },
  url() {
    return 'https://api.github.com/repos/' + GITHUB_REPO + '/contents/' + GITHUB_FILE.split('/').map(encodeURIComponent).join('/');
  },
  async currentSha() {
    const r = await fetch(this.url() + '?ref=' + encodeURIComponent(GITHUB_BRANCH), { headers: this.headers(false) });
    if (r.status === 404) return null;
    if (!r.ok) throw new Error('GitHub ' + r.status);
    const j = await r.json();
    return j.sha;
  },
  async read() {
    const r = await fetch(this.url() + '?ref=' + encodeURIComponent(GITHUB_BRANCH), { headers: this.headers(true) });
    if (r.status === 404) return { data: normalize({}), rev: 'empty' };
    if (!r.ok) throw new Error('GitHub ' + r.status);
    const txt = await r.text();
    const sh = (await this.currentSha()) || 'empty';
    return { data: normalize(JSON.parse(txt)), rev: sh };
  },
  async write(data, baseRev) {
    const sh = await this.currentSha();
    if (baseRev && baseRev !== 'force' && (sh || 'empty') !== baseRev) {
      const e = new Error('conflict'); e.status = 409; throw e;
    }
    const body = {
      message: '[skip render] Cập nhật TKB ' + new Date().toISOString(),
      content: Buffer.from(JSON.stringify(data)).toString('base64'),
      branch: GITHUB_BRANCH,
    };
    if (sh) body.sha = sh;
    const r = await fetch(this.url(), {
      method: 'PUT',
      headers: Object.assign({ 'Content-Type': 'application/json' }, this.headers(false)),
      body: JSON.stringify(body),
    });
    if (r.status === 409 || r.status === 422) { const e = new Error('conflict'); e.status = 409; throw e; }
    if (!r.ok) throw new Error('GitHub ' + r.status);
    const j = await r.json();
    return { rev: j.content && j.content.sha };
  },
};
const backend = STORAGE === 'github' ? ghStore : fileStore;

let cache = null; // {data, rev, at}
async function getData(force) {
  if (!force && cache && Date.now() - cache.at < 30 * 1000) return cache;
  const r = await backend.read();
  cache = { data: r.data, rev: r.rev, at: Date.now() };
  return cache;
}

let writing = Promise.resolve();
function enqueueWrite(fn) {
  const p = writing.then(fn, fn);
  writing = p.catch(() => {});
  return p;
}

/* ---------- định tuyến ---------- */
const INDEX = path.join(__dirname, 'public', 'index.html');
function serveIndex(req, res) {
  fs.readFile(INDEX, (err, buf) => {
    if (err) { res.writeHead(500); res.end('Không đọc được index.html'); return; }
    res.writeHead(200, {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'no-cache',
      'X-Content-Type-Options': 'nosniff',
      'Referrer-Policy': 'same-origin',
    });
    res.end(req.method === 'HEAD' ? undefined : buf);
  });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://x');
  const p = url.pathname;
  try {
    if (p === '/api/health') return send(res, 200, { ok: true, storage: STORAGE });

    if (p === '/api/session' && req.method === 'GET') {
      return send(res, 200, { admin: isAdmin(req), storage: STORAGE, durable: STORAGE === 'github', adminEnabled: !!ADMIN_PIN });
    }

    if (p === '/api/login' && req.method === 'POST') {
      if (!originOk(req)) return send(res, 403, { error: 'Nguồn gốc không hợp lệ' });
      const ip = clientIp(req);
      const wait = lockedOut(ip);
      if (wait) return send(res, 429, { error: 'Đăng nhập sai quá nhiều lần. Thử lại sau ' + Math.ceil(wait / 60000) + ' phút.' });
      const b = await readBody(req);
      if (!ADMIN_PIN || !safeEqual(b.pin || '', ADMIN_PIN)) {
        recordFail(ip);
        return send(res, 401, { error: 'Mã PIN không đúng' });
      }
      fails.delete(ip);
      const cookie = 'tkb_admin=' + encodeURIComponent(makeToken()) + '; HttpOnly; SameSite=Lax; Path=/; Max-Age=' + (SESSION_MS / 1000) + (isHttps(req) ? '; Secure' : '');
      return send(res, 200, { ok: true }, { 'Set-Cookie': cookie });
    }

    if (p === '/api/logout' && req.method === 'POST') {
      if (!originOk(req)) return send(res, 403, { error: 'Nguồn gốc không hợp lệ' });
      return send(res, 200, { ok: true }, { 'Set-Cookie': 'tkb_admin=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0' });
    }

    if (p === '/api/data' && req.method === 'GET') {
      const c = await getData(false);
      return send(res, 200, Object.assign({ rev: c.rev }, c.data));
    }

    if (p === '/api/data' && req.method === 'POST') {
      if (!originOk(req)) return send(res, 403, { error: 'Nguồn gốc không hợp lệ' });
      if (!isAdmin(req)) return send(res, 401, { error: 'Cần đăng nhập quản trị' });
      const b = await readBody(req);
      const d = normalize(b);
      if (!hasRealData(d.store) && !b.allowEmpty) {
        return send(res, 400, { error: 'Dữ liệu trống — không lưu để tránh xoá mất TKB đang công bố.' });
      }
      d.syncedAt = new Date().toISOString();
      const result = await enqueueWrite(async () => {
        const cur = await getData(true);
        const base = b.baseRev || cur.rev;
        if (STORAGE === 'file' && base !== 'force' && base !== cur.rev) {
          const e = new Error('conflict'); e.status = 409; throw e;
        }
        const w = await backend.write(d, base);
        cache = { data: d, rev: w.rev, at: Date.now() };
        return w;
      });
      return send(res, 200, { ok: true, rev: result.rev, syncedAt: d.syncedAt, durable: STORAGE === 'github' });
    }

    if (p.startsWith('/api/')) return send(res, 404, { error: 'Không tìm thấy' });

    if ((p === '/' || p === '/index.html') && (req.method === 'GET' || req.method === 'HEAD')) return serveIndex(req, res);

    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('Không tìm thấy trang');
  } catch (e) {
    const code = e.status || 500;
    if (code === 409) return send(res, 409, { error: 'Có người vừa công bố bản mới hơn bản bạn đang xem.', conflict: true });
    console.error('Lỗi:', p, e.message);
    send(res, code, { error: code === 500 ? 'Lỗi máy chủ: ' + e.message : e.message });
  }
});

server.listen(PORT, () => console.log('TKB đang chạy tại cổng ' + PORT + ' · lưu trữ: ' + STORAGE));
