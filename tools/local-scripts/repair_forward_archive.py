# -*- coding: utf-8 -*-
"""把存档里那条没展开的合并转发补展开(用 res_id 走一遍,写回存档)"""
import io
import json
import sys

import httpx

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SL = r'F:\QQAI\SnowLuma-v2.0.3-win-x64\config\onebot_3660925128.json'
ARCHIVE = r'F:\QQAI\QQ-agent\data\messages\group_1046130381.json'

sl = json.load(open(SL, encoding='utf-8-sig'))
tok = sl['networks']['httpServers'][0]['accessToken']
H = {'Authorization': 'Bearer ' + tok}

data = json.load(open(ARCHIVE, encoding='utf-8'))
msgs = data if isinstance(data, list) else (data.get('messages') or [])

target = None
for m in msgs:
    if '合并转发' in str(m.get('text') or ''):
        target = m
        break

if not target:
    print('存档里没有待展开的转发')
    raise SystemExit

mid = target.get('mid')
print('目标消息 mid =', mid, '| 当前文本 =', target.get('text'))

with httpx.Client(timeout=60) as c:
    ev = c.post('http://127.0.0.1:3101/get_msg', headers=H, json={'message_id': int(mid)}).json()
    segs = (ev.get('data') or {}).get('message') or []
    rid = ''
    for s in segs:
        if s.get('type') == 'forward':
            d = s.get('data') or {}
            rid = d.get('id') or d.get('res_id') or ''
            break
    print('res_id =', rid[:24] + '...' if rid else '(无)')
    if not rid:
        print('拿不到 res_id，放弃')
        raise SystemExit
    r = c.post('http://127.0.0.1:3101/get_forward_msg', headers=H, json={'id': rid}).json()
    nodes = (r.get('data') or {}).get('messages') or []
    print('节点数:', len(nodes))

lines = []
for n in nodes:
    sender = (n.get('sender') or {}).get('nickname') or str(n.get('sender_id') or '?')
    parts = []
    for seg in n.get('message') or []:
        t = seg.get('type')
        if t == 'text':
            parts.append(str((seg.get('data') or {}).get('text', '')))
        elif t == 'image':
            parts.append('[图]')
        elif t == 'face':
            parts.append('[表情]')
    body = ''.join(parts).strip()
    if body:
        lines.append('%s：%s' % (sender, body))

if not lines:
    print('展开后没有文本内容')
    raise SystemExit

expanded = '[合并转发 共 %d 条] %s' % (len(lines), ' / '.join(lines))
target['text'] = expanded[:1500]
json.dump(data, open(ARCHIVE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('已写回存档，前 200 字:')
print(expanded[:200])
