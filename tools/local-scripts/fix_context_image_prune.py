# -*- coding: utf-8 -*-
"""限制上下文里保留的图片数量，防止多轮看图把 token 打爆

症状：一次会话 11 轮、8 次 get_message_images、14.6 万 token，最后卡住不动。
原因：每次看图都会往对话里补一条带 base64 图片的 user 消息，**之后每一轮请求
都会把这些图重新上传一遍**。8 张图 × 每轮 = 请求体积与延迟成倍上涨。

修法：每次请求前裁剪图片——只保留最近 K 条带图消息，更早的把图片部件换成
一行文字说明（[早前查看过的图片已省略]）。文本一律不动，模型仍知道看过什么。
K 默认 2，可用 config.api.keepRecentImages 覆盖（0 = 不裁剪）。
"""
import io
import shutil
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

P = r'F:\QQAI\QQ-agent\src\llm.js'
s = open(P, encoding='utf-8').read()

if 'pruneOldImageParts' in s:
    print('已打过补丁，跳过')
    raise SystemExit

HELPER = '''
/**
 * 裁掉上下文里较早的图片部件。
 *
 * 工具返回的图会以 user 消息（text + image_url）留在对话里，每轮请求都会重发。
 * 连续看 8 次图 = 8 张图要在后面每一轮里重复上传，token 与时延都按倍增长，
 * 表现就是"思考完卡住不动"。这里只留最近 keep 条带图消息，其余替换成文字占位。
 *
 * 只动 image_url / video_url 部件，文本与 tool 消息一律保持原样。
 */
export function pruneOldImageParts(messages, keep = 2) {
  const limit = Number(keep);
  if (!Array.isArray(messages) || !Number.isFinite(limit) || limit < 0) return messages;
  const withMedia = [];
  for (let i = 0; i < messages.length; i++) {
    const c = messages[i]?.content;
    if (!Array.isArray(c)) continue;
    if (c.some((p) => p?.type === 'image_url' || p?.type === 'video_url')) withMedia.push(i);
  }
  if (withMedia.length <= limit) return messages;
  const dropIdx = new Set(withMedia.slice(0, withMedia.length - limit));
  const out = messages.map((m, i) => {
    if (!dropIdx.has(i) || !Array.isArray(m?.content)) return m;
    const kept = m.content.filter((p) => p?.type !== 'image_url' && p?.type !== 'video_url');
    const dropped = m.content.length - kept.length;
    return {
      ...m,
      content: [
        ...kept,
        { type: 'text', text: `[早前查看过的 ${dropped} 张图片已省略，需要重看请再次调用看图工具]` }
      ]
    };
  });
  return out;
}
'''

anchor = 'export async function chatCompletionWithRetry('
idx = s.find(anchor)
assert idx > 0, 'llm.js 未找到插入点'
s = s[:idx] + HELPER.strip() + '\n\n' + s[idx:]

# 在 chatCompletion 内部、组装请求前裁剪
OLD = """export async function chatCompletion({ messages, tools = null, toolChoice = 'auto', temperature = null, signal = null, overrides = null, skillContext = null, maxTokens = 0 }) {"""
NEW = OLD + """
  // 多轮看图时，旧图片每轮都会被重发；只保留最近若干张（config.api.keepRecentImages）
  try {
    const keep = Number(getConfig()?.api?.keepRecentImages);
    messages = pruneOldImageParts(messages, Number.isFinite(keep) ? keep : 2);
  } catch { /* 配置读取失败就按默认裁剪 */ }"""

assert OLD in s, 'llm.js 未找到 chatCompletion 签名'
s = s.replace(OLD, NEW, 1)
shutil.copy2(P, P + '.bak_imgprune')
open(P, 'w', encoding='utf-8').write(s)
print('llm.js: 已加入旧图片裁剪（默认保留最近 2 张）')
