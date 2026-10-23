# -*- coding: utf-8 -*-
"""检查 QQ-agent 会话里合并转发消息的处理情况"""
import glob
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
SEP = chr(92) + chr(92)

files = sorted(glob.glob(r'F:\QQAI\QQ-agent\data\sessions\*.json'))
print('会话文件:', len(files))
shown = 0
for f in files:
    try:
        d = json.load(open(f, encoding='utf-8'))
    except Exception:
        continue
    txt = json.dumps(d, ensure_ascii=False)
    if '合并转发' not in txt and 'read_forward' not in txt:
        continue
    shown += 1
    if shown > 5:
        break
    print('==', os.path.basename(f), '| 状态', d.get('status'), '| 群', d.get('chatKey'))
    for m in d.get('messages') or []:
        s = json.dumps(m, ensure_ascii=False)
        if '合并转发' in s or 'read_forward' in s:
            role = m.get('role')
            tc = m.get('toolCall') or {}
            body = str(m.get('content') or '').replace(chr(10), ' ')[:150]
            print('   [%s] 工具=%s | %s' % (role, tc.get('name') or '-', body[:140]))
    print()
