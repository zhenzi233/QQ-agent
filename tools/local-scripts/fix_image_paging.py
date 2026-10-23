# -*- coding: utf-8 -*-
"""让 get_message_images 支持分页，避免一次塞 30 张图（18MB）导致请求失败

实测：合并转发里 30 张图，平均 452 KB/张 → base64 后约 18 MB，
一次全塞进 image_url 部件，模型接口直接超限失败，表现就是「看不了聊天记录里的图片」。
"""
import io
import shutil
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

P = r'F:\QQAI\QQ-agent\src\tools.js'
s = open(P, encoding='utf-8').read()

OLD_DESC = ("    description: '查看某条消息里的图片/表情（视觉模型可以直接看懂）。消息文本出现 [图片] 时可用。"
            "id 用聊天记录里每条消息前的 #数字。',")
NEW_DESC = ("    description: '查看某条消息里的图片/表情（视觉模型可以直接看懂）。消息文本出现 [图片] 时可用。"
            "id 用聊天记录里每条消息前的 #数字。一条消息里图片很多时（比如合并转发）每次最多看 4 张，"
            "用 offset 往后翻，不要一次要求全部。',")

OLD_PARAMS = """      properties: { messageId: { type: ['integer', 'string'], description: 'QQ 消息 id（聊天记录里的 #数字，可能为负数）' } },
      required: ['messageId']"""
NEW_PARAMS = """      properties: {
        messageId: { type: ['integer', 'string'], description: 'QQ 消息 id（聊天记录里的 #数字，可能为负数）' },
        offset: { type: 'integer', description: '跳过前 N 张，默认 0；图多时用它往后翻' },
        limit: { type: 'integer', description: '本次最多看几张，默认 4，最大 6' }
      },
      required: ['messageId']"""

OLD_BODY = """        const entry = ctx.store.findByMid(ctx.chatKey, args.messageId);
        if (!entry) return err(`在当前会话找不到消息 ${args.messageId}。${midHint(ctx)}`);
        const urls = (entry.media || []).filter((m) => m.kind === 'image' && m.url).map((m) => m.url);
        if (!urls.length) return ok(`消息 ${args.messageId} 没有可查看的图片`);
        const results = [];
        const failed = [];
        for (const url of urls) {"""
NEW_BODY = """        const entry = ctx.store.findByMid(ctx.chatKey, args.messageId);
        if (!entry) return err(`在当前会话找不到消息 ${args.messageId}。${midHint(ctx)}`);
        const allUrls = (entry.media || []).filter((m) => m.kind === 'image' && m.url).map((m) => m.url);
        if (!allUrls.length) return ok(`消息 ${args.messageId} 没有可查看的图片`);
        // 分页：一条消息（尤其合并转发）可能带几十张图，全塞进去 base64 会到十几 MB，
        // 模型接口直接 400/413，表现就是"看不了图"。默认一次 4 张，用 offset 往后翻。
        const offset = Math.max(0, Number(args.offset) || 0);
        const limit = Math.min(6, Math.max(1, Number(args.limit) || 4));
        const urls = allUrls.slice(offset, offset + limit);
        if (!urls.length) {
          return ok(`消息 ${args.messageId} 共 ${allUrls.length} 张图，offset=${offset} 已经超出范围`);
        }
        const results = [];
        const failed = [];
        for (const url of urls) {"""

OLD_TAIL = """        const built = getImagePartsOrVideo(`消息 ${args.messageId} 的内容${note}：${what}。`, results);
        return built;"""
NEW_TAIL = """        const shownTo = offset + urls.length;
        const more = shownTo < allUrls.length
          ? `（这条消息共 ${allUrls.length} 张，本次看第 ${offset + 1}-${shownTo} 张；还有 ${allUrls.length - shownTo} 张，用 offset=${shownTo} 继续）`
          : `（这条消息共 ${allUrls.length} 张，已全部看完）`;
        const built = getImagePartsOrVideo(`消息 ${args.messageId} 的内容${note}：${what}。${more}`, results);
        return built;"""

changes = 0
for old, new, label in ((OLD_DESC, NEW_DESC, '描述'),
                        (OLD_PARAMS, NEW_PARAMS, '参数'),
                        (OLD_BODY, NEW_BODY, '分页逻辑'),
                        (OLD_TAIL, NEW_TAIL, '结果说明')):
    if new.split('\n')[0].strip() in s and label != '描述':
        print('%s: 已打过补丁，跳过' % label)
        continue
    if old in s:
        s = s.replace(old, new, 1)
        changes += 1
        print('%s: 已替换' % label)
    else:
        print('%s: 未找到锚点！' % label)

if changes:
    shutil.copy2(P, P + '.bak_imgpage')
    open(P, 'w', encoding='utf-8').write(s)
    print('已写入（备份 .bak_imgpage）')
