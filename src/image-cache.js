// 图片本地化：消息入库时就把图片字节存到本地，之后看图读盘。
//
// ── 为什么 ────────────────────────────────────────────────────────────────
// QQ 图床的 URL 有时效（rkey 约 1 小时），群里「过一会儿再让它看看这张图」
// 就会 400。更糟的是老 gchat 链接也会随 rkey 失效。所以趁 URL 新鲜时抓一次，
// 之后永远读本地。
//
// ── 边界 ──────────────────────────────────────────────────────────────────
//   · 失败**不影响**入库：抓不到就算了，media 里仍留着原 URL，工具会再试
//   · 单张上限、总容量上限、保留天数都可配（config.media.localize）
//   · 文件按内容 sha1 命名 → 同一张图在多个群/多次出现只存一份
//   · 索引 `data/images/index.json`：mid → { sha1, file, bytes, at, chatKey }
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

import { DATA_DIR, getConfig } from './config.js';
import { needsRKey, withRKey, pickRKey } from './image-url.js';
import { validateImageUrl, safeFetchBinary } from './safe-fetch.js';

const DIR = path.join(DATA_DIR, 'images');
const INDEX_FILE = path.join(DIR, 'index.json');

const DEFAULTS = {
  enabled: true,
  maxBytes: 8 * 1024 * 1024,
  keepDays: 14,
  maxTotalMb: 2048,
};

let index = null;
let indexDirty = false;
let flushTimer = null;

function conf() {
  const c = (getConfig().media || {}).localize || {};
  return {
    enabled: c.enabled !== false,
    maxBytes: Number(c.maxBytes) > 0 ? Number(c.maxBytes) : DEFAULTS.maxBytes,
    keepDays: Number(c.keepDays) > 0 ? Number(c.keepDays) : DEFAULTS.keepDays,
    maxTotalMb: Number(c.maxTotalMb) > 0 ? Number(c.maxTotalMb) : DEFAULTS.maxTotalMb
  };
}

function loadIndex() {
  if (index) return index;
  try {
    index = JSON.parse(fs.readFileSync(INDEX_FILE, 'utf8')) || {};
  } catch {
    index = {};
  }
  return index;
}

function scheduleFlush() {
  indexDirty = true;
  if (flushTimer) return;
  flushTimer = setTimeout(() => {
    flushTimer = null;
    flush();
  }, 1500);
  if (flushTimer.unref) flushTimer.unref();
}

function flush() {
  if (!indexDirty) return;
  try {
    fs.mkdirSync(DIR, { recursive: true });
    const tmp = `${INDEX_FILE}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify(index));
    fs.renameSync(tmp, INDEX_FILE);
    indexDirty = false;
  } catch { /* 索引写失败不影响主流程 */ }
}

function sniffExt(buf) {
  if (!buf || buf.length < 12) return 'bin';
  if (buf[0] === 0x89 && buf[1] === 0x50) return 'png';
  if (buf[0] === 0xff && buf[1] === 0xd8) return 'jpg';
  if (buf.slice(0, 3).toString('latin1') === 'GIF') return 'gif';
  if (buf.slice(0, 4).toString('latin1') === 'RIFF' && buf.slice(8, 12).toString('latin1') === 'WEBP') return 'webp';
  if (buf[0] === 0x42 && buf[1] === 0x4d) return 'bmp';
  return 'bin';
}

const RKEY_CACHE = { at: 0, primary: null, alternate: null };

async function signedCandidates(onebot, url, chatKey) {
  if (!needsRKey(url)) return [url];
  const isGroup = String(chatKey || '').startsWith('group:');
  const fresh = Date.now() - RKEY_CACHE.at < 5 * 60 * 1000;
  if (!fresh || !RKEY_CACHE.primary) {
    try {
      const res = await onebot?.call?.('get_rkey', {});
      const { primary, alternate } = pickRKey(res, { isGroup });
      RKEY_CACHE.primary = primary;
      RKEY_CACHE.alternate = alternate;
      RKEY_CACHE.at = Date.now();
    } catch { /* 没 rkey 就只试原 URL */ }
  }
  const out = [];
  if (RKEY_CACHE.primary) out.push(withRKey(url, RKEY_CACHE.primary.rkey));
  if (RKEY_CACHE.alternate) out.push(withRKey(url, RKEY_CACHE.alternate.rkey));
  out.push(url);
  return out;
}

/**
 * 下载并保存一条消息里的所有图片。返回成功保存的条数。
 * 调用方 fire-and-forget：内部把异常都吞掉，只记日志。
 */
export async function localizeMessage({ onebot, chatKey, mid, media = [] }) {
  const c = conf();
  if (!c.enabled) return 0;
  const images = (media || []).filter((m) => m && m.kind === 'image' && (m.url || m.file));
  if (!images.length) return 0;
  const idx = loadIndex();
  let saved = 0;
  for (const m of images) {
    try {
      const candidates = m.url
        ? await signedCandidates(onebot, m.url, chatKey)
        : [];
      let buf = null;
      let lastError = null;
      for (const url of candidates) {
        try {
          const safe = await validateImageUrl(url);
          const r = await safeFetchBinary(safe);
          if (r?.buffer?.length) { buf = r.buffer; break; }
        } catch (e) { lastError = e; }
      }
      if (!buf && m.file && onebot) {
        // 兜底：让协议端按 file 名下载（它走 QQ 内部通道，不依赖 URL 时效）
        try { buf = await downloadViaStream(onebot, m.file); } catch (e) { lastError = e; }
      }
      if (!buf) continue;
      if (buf.length > c.maxBytes) continue;
      const sha1 = crypto.createHash('sha1').update(buf).digest('hex');
      const ext = sniffExt(buf);
      const file = `${sha1}.${ext}`;
      const abs = path.join(DIR, file);
      if (!fs.existsSync(abs)) {
        fs.mkdirSync(DIR, { recursive: true });
        fs.writeFileSync(abs, buf);
      }
      const key = String(mid ?? '');
      if (key) idx[key] = { sha1, file, bytes: buf.length, at: Date.now(), chatKey: String(chatKey || '') };
      // 同一条消息多张图：用 mid-序号 区分
      if (key && images.length > 1) idx[`${key}#${saved}`] = idx[key];
      saved += 1;
      scheduleFlush();
    } catch { /* 单张失败不影响其它 */ }
  }
  return saved;
}

/** 用 SnowLuma 的流式下载动作按 file 名取字节（失败返回 null）。 */
function downloadViaStream(onebot, file) {
  return new Promise((resolve) => {
    let settled = false;
    const done = (v) => { if (!settled) { settled = true; resolve(v); } };
    try {
      onebot?.downloadStream?.('download_file_image_stream', { file }, 15000)
        ?.then((buf) => done(buf))
        ?.catch(() => done(null));
      setTimeout(() => done(null), 16000);
    } catch { done(null); }
  });
}

/** 按消息 id 找本地文件（绝对路径），没有返回空串。 */
export function findLocalByMid(mid) {
  const idx = loadIndex();
  const hit = idx[String(mid ?? '')];
  if (!hit?.file) return '';
  const abs = path.join(DIR, hit.file);
  try { return fs.existsSync(abs) ? abs : ''; } catch { return ''; }
}

/** 按 sha1 / 文件名找本地文件。 */
export function findLocalByFile(fileOrSha) {
  const key = String(fileOrSha || '').trim();
  if (!key) return '';
  const sha = key.replace(/\.[a-z0-9]+$/i, '');
  const idx = loadIndex();
  for (const v of Object.values(idx)) {
    if (v?.sha1 === sha || v?.file === key) {
      const abs = path.join(DIR, v.file);
      try { return fs.existsSync(abs) ? abs : ''; } catch { return ''; }
    }
  }
  return '';
}

/** 清理：按保留天数与总容量上限，从最老的开始删。返回删除数量。 */
export function pruneImages() {
  const c = conf();
  const idx = loadIndex();
  let removed = 0;
  const cutoff = Date.now() - c.keepDays * 24 * 3600 * 1000;
  const entries = Object.entries(idx);
  // 1) 过期
  for (const [k, v] of entries) {
    if (!v || (v.at || 0) >= cutoff) continue;
    if (v.file) { try { fs.unlinkSync(path.join(DIR, v.file)); } catch {} }
    delete idx[k];
    removed += 1;
  }
  // 2) 超容量（按 at 从旧到新删）
  let total = 0;
  const stat = [];
  for (const [k, v] of Object.entries(idx)) {
    if (!v?.file) continue;
    const p = path.join(DIR, v.file);
    let size = 0;
    try { size = fs.statSync(p).size; } catch { size = 0; }
    total += size;
    stat.push({ k, v, size, at: v.at || 0 });
  }
  const budget = c.maxTotalMb * 1024 * 1024;
  if (total > budget) {
    stat.sort((a, b) => a.at - b.at);
    for (const item of stat) {
      if (total <= budget) break;
      try { fs.unlinkSync(path.join(DIR, item.v.file)); } catch {}
      delete idx[item.k];
      total -= item.size;
      removed += 1;
    }
  }
  if (removed) { indexDirty = true; flush(); }
  return removed;
}

export function imageCacheStats() {
  const idx = loadIndex();
  let bytes = 0;
  for (const v of Object.values(idx)) bytes += Number(v?.bytes) || 0;
  return { entries: Object.keys(idx).length, bytes, dir: DIR };
}
