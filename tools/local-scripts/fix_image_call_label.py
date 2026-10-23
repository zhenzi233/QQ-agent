# -*- coding: utf-8 -*-
"""修复：多次看图调用时，图片补发消息没说明"这张图属于哪条消息"

症状：一条消息里/一批消息里有多张图，模型把第一张说成最后一张的内容。

原因：工具返回的媒体不能塞进 tool 消息，代码会另发一条 user 消息补图，文案是
`[系统：以下是工具 get_message_images 返回的 1 张图片，请直接"看"了回应]` ——
**没有带调用参数**。连续两次 get_message_images（比如先看 #A 再看 #B）时，
两条补图消息长得一模一样，模型只能靠顺序猜，于是出现"引用第一个却描述了最后一个"。

修法：补图消息带上这次调用的参数（messageId 等），并明确写出"图属于本次调用"。
"""
import io
import shutil
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

P = r'F:\QQAI\QQ-agent\src\orchestrator.js'
s = open(P, encoding='utf-8').read()

OLD = """          imageUserMessages.push({
            role: 'user',
            content: [
              { type: 'text', text: `[系统：以下是工具 ${name} 返回的 ${what}，请直接"看"了回应]` },
              ...media
            ]
          });"""

NEW = """          // 补图消息必须带上"这次调用是谁、参数是什么"，否则连续两次看图
          // （先 #A 再看 #B）时两条补图消息文本完全相同，模型只能靠顺序猜，
          // 就会出现"说的是第一条图的 mid、描述的却是最后一张图"。
          const rawArgs = safeParse(argsRaw) ?? {};
          const argBrief = Object.entries(rawArgs)
            .map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`)
            .join(' ')
            .slice(0, 120);
          const callLabel = argBrief ? `${name}（${argBrief}）` : name;
          imageUserMessages.push({
            role: 'user',
            content: [
              { type: 'text', text: `[系统：以下是工具 ${callLabel} 返回的 ${what}，请直接"看"了回应；`
                + `这些图只属于上面这一次调用，不要和别的调用返回的图混起来]` },
              ...media
            ]
          });"""

assert OLD in s, '未找到补图消息构造处'
assert 'callLabel' not in s, '已打过补丁'
shutil.copy2(P, P + '.bak_imglabel')
s = s.replace(OLD, NEW, 1)
open(P, 'w', encoding='utf-8').write(s)
print('已给补图消息加上调用参数标注')
