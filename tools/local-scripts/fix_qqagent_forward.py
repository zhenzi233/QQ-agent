# -*- coding: utf-8 -*-
"""修复 QQ-agent 展不开合并转发的问题

根因:SnowLuma 的 get_forward_msg 只认转发卡片的 res_id(长字符串),传 message_id
会退回把 message_id 当 id 用,QQ 侧报 "download forward message payload is empty"。
正确做法:先用 get_msg 拿到该消息的 forward 段 data.id,再用 { id } 调用。
"""
import io
import os
import shutil
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT = r'F:\QQAI\QQ-agent'
ONEBOT = os.path.join(ROOT, 'src', 'onebot.js')
APP = os.path.join(ROOT, 'src', 'app.js')
TOOLS = os.path.join(ROOT, 'src', 'tools.js')

helper = '''
/**
 * 解析合并转发的 res_id。
 *
 * SnowLuma/NapCat 的 get_forward_msg 只认转发卡片上的 res_id（长字符串）；
 * 传 message_id 时它会退回把 message_id 当 id 用，QQ 侧返回
 * "download forward message payload is empty"（2026-10-23 实测）。
 * 所以先 get_msg 取该消息的 forward 段 data.id，取不到再让调用方走旧路。
 */
export async function resolveForwardId(onebot, messageId) {
  try {
    const ev = await onebot.call('get_msg', { message_id: Number(messageId) });
    const segs = ev?.message ?? ev?.data?.message ?? [];
    for (const seg of Array.isArray(segs) ? segs : []) {
      if (!seg || seg.type !== 'forward') continue;
      const d = seg.data ?? {};
      const id = d.id ?? d.res_id ?? d.forward_id;
      if (id) return String(id);
    }
  } catch { /* 取不到就走 message_id 旧路 */ }
  return '';
}
'''

# ---------- 1. onebot.js 加 helper ----------
s = open(ONEBOT, encoding='utf-8').read()
if 'resolveForwardId' not in s:
    shutil.copy2(ONEBOT, ONEBOT + '.bak_forward')
    anchor = 'export async function expandForwardNodes'
    idx = s.find(anchor)
    if idx < 0:
        anchor = 'export function forwardIdFromData'
        idx = s.find(anchor)
    assert idx > 0, 'onebot.js 找不到插入点'
    s = s[:idx] + helper.strip() + '\n\n' + s[idx:]
    open(ONEBOT, 'w', encoding='utf-8').write(s)
    print('onebot.js: 已加 resolveForwardId')
else:
    print('onebot.js: 已存在')

# ---------- 2. app.js 收消息时优先用 res_id ----------
s2 = open(APP, encoding='utf-8').read()
old_call = "const r = await onebot.call('get_forward_msg', { message_id: Number(event.message_id) });"
if 'resolveForwardId' not in s2:
    shutil.copy2(APP, APP + '.bak_forward')
    assert old_call in s2, 'app.js 找不到 get_forward_msg 调用点'
    new_call = ("const fwdId = await resolveForwardId(onebot, event.message_id).catch(() => '');\n"
                "        const r = fwdId\n"
                "          ? await onebot.call('get_forward_msg', { id: fwdId })\n"
                "          : await onebot.call('get_forward_msg', { message_id: Number(event.message_id) });")
    s2 = s2.replace(old_call, new_call, 1)
    # 补 import
    imp_old = "import { OneBotClient, segmentsToText, extractMediaFromSegments, expandForwardNodes } from './onebot.js';"
    imp_new = ("import { OneBotClient, segmentsToText, extractMediaFromSegments, expandForwardNodes, "
               "resolveForwardId } from './onebot.js';")
    assert imp_old in s2, 'app.js 找不到 import 行'
    s2 = s2.replace(imp_old, imp_new, 1)
    open(APP, 'w', encoding='utf-8').write(s2)
    print('app.js: 收消息时优先用 res_id 展开')
else:
    print('app.js: 已存在')

# ---------- 3. tools.js read_forward 也走 res_id ----------
s3 = open(TOOLS, encoding='utf-8').read()
old_tool = "const r = await ctx.onebot.call('get_forward_msg', { message_id: Number(entry.mid) });"
if 'resolveForwardId' not in s3:
    shutil.copy2(TOOLS, TOOLS + '.bak_forward')
    assert old_tool in s3, 'tools.js 找不到 get_forward_msg 调用点'
    new_tool = ("const fwdId = await resolveForwardId(ctx.onebot, entry.mid).catch(() => '');\n"
                "        const r = fwdId\n"
                "          ? await ctx.onebot.call('get_forward_msg', { id: fwdId })\n"
                "          : await ctx.onebot.call('get_forward_msg', { message_id: Number(entry.mid) });")
    s3 = s3.replace(old_tool, new_tool, 1)
    # 补 import：tools.js 从 onebot.js 引入了什么
    lines = s3.split('\n')
    patched = False
    for i, ln in enumerate(lines):
        if ln.startswith('import ') and "'./onebot.js'" in ln:
            if ln.rstrip().endswith(';'):
                lines[i] = ln.rstrip()[:-2] + ', resolveForwardId } from \'./onebot.js\';'
            patched = True
            break
    if patched:
        s3 = '\n'.join(lines)
    else:
        s3 = "import { resolveForwardId } from './onebot.js';\n" + s3
    open(TOOLS, 'w', encoding='utf-8').write(s3)
    print('tools.js: read_forward 优先用 res_id')
else:
    print('tools.js: 已存在')
