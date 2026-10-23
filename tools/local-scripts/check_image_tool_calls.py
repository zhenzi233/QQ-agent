# -*- coding: utf-8 -*-
"""检查 QQ-agent 会话里 get_message_images / read_forward 的调用结果"""
import glob
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

files = sorted(glob.glob(r'F:\QQAI\QQ-agent\data\sessions\*.json'), key=os.path.getmtime)[-25:]
found = 0
for f in files:
    try:
        d = json.load(open(f, encoding='utf-8'))
    except Exception:
        continue
    msgs = d.get('messages') or []
    for i, m in enumerate(msgs):
        tc = m.get('toolCall') or {}
        name = str(tc.get('name') or '')
        if name not in ('get_message_images', 'read_forward', 'view_sticker'):
            continue
        found += 1
        # 后面的 tool 结果消息
        res = ''
        for j in range(i + 1, min(i + 3, len(msgs))):
            mm = msgs[j]
            if mm.get('role') == 'tool' or mm.get('toolResult') is not None:
                res = json.dumps(mm.get('toolResult') or mm.get('content') or '', ensure_ascii=False)
                break
        print('%s | %-20s args=%s' % (os.path.basename(f)[:12], name,
                                      json.dumps(tc.get('arguments') or {}, ensure_ascii=False)[:80]))
        print('   -> %s' % res[:260].replace(chr(10), ' '))
print('命中调用:', found)
