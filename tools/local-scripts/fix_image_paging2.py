# -*- coding: utf-8 -*-
"""给 get_message_images 加分页（按行定位，避免长串匹配失败）"""
import io
import re
import shutil
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

P = r'F:\QQAI\QQ-agent\src\tools.js'
lines = open(P, encoding='utf-8').read().split('\n')

start = None
for i, ln in enumerate(lines):
    if "id: 'get_message_images'" in ln:
        start = i
        break
if start is None:
    print('找不到工具定义')
    raise SystemExit

end = None
for j in range(start, min(start + 60, len(lines))):
    if 'for (const url of urls)' in lines[j]:
        end = j
        break
if end is None:
    print('找不到执行块')
    raise SystemExit

block = lines[start:end]
# 1) 参数：把单行 properties 换成三行
for k, ln in enumerate(block):
    if ln.strip().startswith('properties: { messageId:'):
        indent = ln[:len(ln) - len(ln.lstrip())]
        block[k:k + 1] = [
            indent + 'properties: {',
            indent + "  messageId: { type: ['integer', 'string'], description: 'QQ 消息 id（聊天记录里的 #数字，可能为负数）' },",
            indent + "  offset: { type: 'integer', description: '跳过前 N 张，默认 0；图多时用它往后翻' },",
            indent + "  limit: { type: 'integer', description: '本次最多看几张，默认 4，最大 6' }",
            indent + '},',
        ]
        break

# 2) 取图逻辑：改成 allUrls + 分页
out = []
i = 0
while i < len(block):
    ln = block[i]
    st = ln.strip()
    if st.startswith('const urls = (entry.media || [])'):
        indent = ln[:len(ln) - len(ln.lstrip())]
        out.append(indent + "const allUrls = (entry.media || []).filter((m) => m.kind === 'image' && m.url).map((m) => m.url);")
        out.append(indent + 'if (!allUrls.length) return ok(`消息 ${args.messageId} 没有可查看的图片`);')
        out.append(indent + '// 分页：一条消息（尤其合并转发）可能带几十张图，一次全塞 base64 会到十几 MB，')
        out.append(indent + '// 模型接口直接 400/413，表现就是"看不到聊天记录里的图片"。默认一次 4 张。')
        out.append(indent + 'const offset = Math.max(0, Number(args.offset) || 0);')
        out.append(indent + 'const limit = Math.min(6, Math.max(1, Number(args.limit) || 4));')
        out.append(indent + 'const urls = allUrls.slice(offset, offset + limit);')
        out.append(indent + 'if (!urls.length) {')
        out.append(indent + '  return ok(`消息 ${args.messageId} 共 ${allUrls.length} 张图，offset=${offset} 已经超出范围`);')
        out.append(indent + '}')
        # 跳过原来的 urls 赋值行与紧接着的 urls.length 检查行
        i += 1
        if i < len(block) and block[i].strip().startswith('if (!urls.length)'):
            i += 2  # 跳过 if 行
            # 若还有 } 收尾（原写法是单行 if）则无需处理
        continue
    out.append(ln)
    i += 1

new_lines = lines[:start] + out + lines[end:]
shutil.copy2(P, P + '.bak_imgpage2')
open(P, 'w', encoding='utf-8').write('\n'.join(new_lines))
print('分页补丁已写入')
