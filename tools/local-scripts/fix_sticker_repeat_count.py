# -*- coding: utf-8 -*-
"""给表情包加「本群第 N 次」计数:模型能看到这是反复出现的同一个表情

配合上一个补丁(渲染成 [表情包#指纹]),这里在入库时把该指纹在本群的累计次数
写进文本:第二次起变成 [表情包#2A29FE2F 第3次]，模型就知道「又来了」。
计数存在 data/sticker-seen.json,按会话隔离,重启不丢。
"""
import io
import shutil
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

P = r'F:\QQAI\QQ-agent\src\app.js'
s = open(P, encoding='utf-8').read()

if 'sticker-seen.json' in s:
    print('已打过补丁，跳过')
    raise SystemExit

HELPER = '''
// ── 表情包重复识别计数（2026-10-23）────────────────────────────────
// 群友反复发同一个表情时,模型只看到 `[图片]` 会当成第一次见。
// onebot.js 已把它渲染成 `[表情包#指纹]`;这里补上「本群第几次」,
// 让"又发这个"这种反应成为可能。按会话隔离,存 data/sticker-seen.json。
const STICKER_SEEN_FILE = path.join(DATA_DIR, 'sticker-seen.json');
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
}

function annotateStickerRepeats(text, chatKey) {
  if (!text || !text.includes('[表情包#')) return text;
  return text.replace(/\\[表情包#([0-9A-F]{8})\\]/g, (whole, fp) => {
    const n = bumpStickerSeen(chatKey, fp);
    return n > 1 ? `[表情包#${fp} 本群第${n}次]` : whole;
  });
}

'''

anchor = 'export function createApp('
idx = s.find(anchor)
assert idx > 0, 'app.js 找不到 createApp'
s = s[:idx] + HELPER.strip() + '\n\n' + s[idx:]

# 在入库前套用注解：找到 appendIncoming 调用处的 text 变量
OLD = """    const entry = store.appendIncoming(`${kind}:${id}`, {"""
NEW = """    // 表情包重复计数：同一张表情在本群第几次出现，让模型能说"又发这个"
    text = annotateStickerRepeats(text, `${kind}:${id}`);

    const entry = store.appendIncoming(`${kind}:${id}`, {"""

assert OLD in s, '找不到 appendIncoming 调用点'
s = s.replace(OLD, NEW, 1)

shutil.copy2(P, P + '.bak_stickerhit')
open(P, 'w', encoding='utf-8').write(s)
print('已写入：表情包重复计数')
