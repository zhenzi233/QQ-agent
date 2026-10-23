# -*- coding: utf-8 -*-
"""表情包本群计数改为「按天统计」:今天的次数不带进明天

原实现只按会话+指纹累加,永久累计。改为每天零点按本地日期切换:
文件结构 { day: 'YYYY-MM-DD', chats: { chatKey: { fp: n } } },
跨天时整体重置(旧结构自动迁移,不会报错)。
"""
import io
import shutil
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

P = r'F:\QQAI\QQ-agent\src\app.js'
s = open(P, encoding='utf-8').read()

OLD = """const STICKER_SEEN_FILE = path.join(DATA_DIR, 'sticker-seen.json');
let stickerSeenCache = null;

function bumpStickerSeen(chatKey, fp) {
  try {
    if (!stickerSeenCache) {
      try { stickerSeenCache = JSON.parse(fs.readFileSync(STICKER_SEEN_FILE, 'utf8')); }
      catch { stickerSeenCache = {}; }
    }
    const perChat = stickerSeenCache[chatKey] || (stickerSeenCache[chatKey] = {});
    perChat[fp] = (Number(perChat[fp]) || 0) + 1;
    fs.writeFileSync(STICKER_SEEN_FILE, JSON.stringify(stickerSeenCache));
    return perChat[fp];
  } catch { return 1; }
}"""

NEW = """const STICKER_SEEN_FILE = path.join(DATA_DIR, 'sticker-seen.json');
let stickerSeenCache = null;   // { day, chats: { chatKey: { fp: n } } }

// 本地日期(YYYY-MM-DD)。用本地时区而不是 UTC：跨天要对得上群友的作息,
// 北京时间 0 点清零才符合"今天的次数"这个说法。
function stickerDayKey(now = Date.now()) {
  const d = new Date(now);
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function loadStickerSeen(day) {
  if (stickerSeenCache && stickerSeenCache.day === day) return stickerSeenCache;
  let raw = null;
  try { raw = JSON.parse(fs.readFileSync(STICKER_SEEN_FILE, 'utf8')); }
  catch { raw = null; }
  // 旧结构(直接是 {chatKey:{fp:n}})自动迁移成按天结构，跨天即视为新的一天
  const chats = raw && typeof raw === 'object' && raw.chats ? raw.chats
    : (raw && typeof raw === 'object' ? raw : {});
  const sameDay = Boolean(raw && raw.day === day);
  stickerSeenCache = { day, chats: sameDay ? chats : {} };
  return stickerSeenCache;
}

function bumpStickerSeen(chatKey, fp) {
  try {
    const store = loadStickerSeen(stickerDayKey());
    const perChat = store.chats[chatKey] || (store.chats[chatKey] = {});
    perChat[fp] = (Number(perChat[fp]) || 0) + 1;
    fs.writeFileSync(STICKER_SEEN_FILE, JSON.stringify(store));
    return perChat[fp];
  } catch { return 1; }
}"""

assert OLD in s, '未找到原计数器实现'
assert 'stickerDayKey' not in s, '已打过补丁'
shutil.copy2(P, P + '.bak_stickday')
s = s.replace(OLD, NEW, 1)
open(P, 'w', encoding='utf-8').write(s)
print('已改为按天计数')
