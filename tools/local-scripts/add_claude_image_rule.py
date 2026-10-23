# -*- coding: utf-8 -*-
"""给 Claude 人设加「群友发图就去看并评价」的规则

QQ-agent 的人设存在两处:
1. customPersonas[] 里的人设模板(可复用)
2. personaByChat[<会话>].roleText —— 实际生效的那份
两边都要改,否则只改模板不会影响正在用的会话。
"""
import io
import json
import os
import sys
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

CFG = r'F:\QQAI\QQ-agent\data\config.json'
MARK = '看图规则'

BLOCK = '''十六、看图规则
群里有人发图片（不是表情包）时，先真的看那张图，再针对图本身说一句评价：

说清楚你看到了什么——画面主体、在做什么、氛围是什么样。不要只说「看到了」「不错」「挺好的」，那是没看。

可以说哪里有意思、哪里怪、像什么，或者顺着上下文接一句吐槽。评价是你自己的判断，不是图片说明。

一条就够。不写图片解说，不做百科式描述，不列「图中可以看到」。

看不清或者图片没加载出来，就直说「这图我没看到」或者「打不开」，不要瞎猜内容。

图是别人的自拍或截图时，评内容，不评长相加身材。

如果这张图跟你正在聊的话题有关，优先接话题；无关就纯粹评图，不硬扯。

'''

OLD_LINE = '别人发图/表情包，能看就看，看到会认真回一句；看不懂就“这个我没看懂”，不装。'
NEW_LINE = ('别人发图/表情包，能看就看。图片要真的看了再评（规则见「十六、看图规则」），'
            '看不懂就“这个我没看懂”，不装。')

cfg = json.load(open(CFG, encoding='utf-8'))
changed = []


def patch_text(text, label):
    if not text or MARK in text:
        return text, False
    t = text.replace(OLD_LINE, NEW_LINE)
    # 插到「十五、总原则」之前；找不到就追加到末尾
    anchor = '十五、总原则'
    if anchor in t:
        t = t.replace(anchor, BLOCK + anchor, 1)
    else:
        t = t.rstrip() + '\n\n' + BLOCK
    return t, True


for p in cfg.get('customPersonas') or []:
    if str(p.get('name')) == 'Claude':
        new, ok = patch_text(str(p.get('text') or ''), 'customPersonas.Claude')
        if ok:
            p['text'] = new
            changed.append('customPersonas.Claude')

for key, val in (cfg.get('personaByChat') or {}).items():
    if not isinstance(val, dict):
        continue
    if 'Claude' not in str(val.get('roleText') or '')[:80]:
        continue
    new, ok = patch_text(str(val.get('roleText') or ''), key)
    if ok:
        val['roleText'] = new
        changed.append('personaByChat[%s]' % key)

if changed:
    cfg['updatedAt'] = datetime.now().isoformat()
    json.dump(cfg, open(CFG, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

print('改动位置:', changed if changed else '(无，可能已存在)')
for k in changed:
    print('  -', k)
