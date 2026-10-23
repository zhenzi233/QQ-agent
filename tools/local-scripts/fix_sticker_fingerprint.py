# -*- coding: utf-8 -*-
"""让 QQ-agent 能认出「同一个表情包」

问题:群友发的表情包和普通图片都渲染成 `[图片]`,模型无法判断这是同一个表情
反复出现,于是每次反应都像第一次见。

改法:图片段带 summary('[动画表情]') 或文件名像 md5 时,渲染成
`[表情包#2A29FE2F]`(取文件名前 8 位),普通图片保持 `[图片]`。
模型靠这个短指纹就能看出「这个表情刚发过」。
"""
import io
import shutil
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

P = r'F:\QQAI\QQ-agent\src\onebot.js'
s = open(P, encoding='utf-8').read()

OLD = "      case 'image': out.push('[图片]'); break;"
NEW = """      case 'image': {
        // 表情包与普通图片要分开标：否则模型看到的永远是同一个 `[图片]`，
        // 分不出「同一个表情又发了一次」（2026-10-23 用户反馈：反应像第一次见）。
        // 指纹取协议端文件名前 8 位（QQ 侧就是 md5），同一张图永远同一个指纹。
        const summary = String(d.summary ?? '');
        const base = String(d.file ?? '').split(/[\\\\/]/).pop() || '';
        const fp = /^[0-9A-Fa-f]{16,}/.exec(base) ? base.slice(0, 8).toUpperCase() : '';
        const isSticker = summary.includes('动画表情') || summary.includes('表情')
          || /\\{\\}\\s*$/.test(summary) || Boolean(d.emoji_id) || Boolean(d.key);
        if (isSticker) out.push(fp ? `[表情包#${fp}]` : '[表情包]');
        else out.push('[图片]');
        break;
      }"""

if '表情包#' in s:
    print('已打过补丁，跳过')
else:
    assert OLD in s, '未找到 image 分支'
    shutil.copy2(P, P + '.bak_stickerfp')
    s = s.replace(OLD, NEW, 1)
    open(P, 'w', encoding='utf-8').write(s)
    print('已打补丁：表情包带指纹')
