# -*- coding: utf-8 -*-
"""引用消息里的图片/表情能看 —— 修「引用的那张图我这边打不开」

现象：群友引用一张表情/图片问「这是什么意思」，机器人回「引用的那张图打不开，只看到个头像」。
原因：`resolveReply` 把非文本段直接映射成 CQ 类型名（`[image]`），而且**没带引用消息的 id**，
     模型既不知道那是图片，也没有可用的参数去调 get_message_images。
改法：
  ① 段落映射成人类可读的占位符（[图片]/[表情]/[表情包]/[合并转发]）
  ② 把引用消息的 id 一并带出，并在文本里标成 `#id`
  ③ 明确提示「引用的图片可以用 get_message_images 看」，让模型有行动路径
"""
import io
import shutil
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ---------- 1) app.js：resolveReply 结构化 ----------
P1 = r'F:\QQAI\QQ-agent\src\app.js'
s = open(P1, encoding='utf-8').read()

if '以 #id 标注' in s or 'resolveReplyDetailed' in s:
    print('app.js: 已打过补丁')
else:
    old = """  async function resolveReply(messageId) {
    try {
      const msg = await onebot.getMsg(messageId);
      const senderName = msg?.sender?.card || msg?.sender?.nickname || '';
      let text = '';
      if (Array.isArray(msg?.message)) {
        text = msg.message.map((s) => (s.type === 'text' ? s.data?.text ?? '' : `[${s.type}]`)).join('').trim();
      } else if (typeof msg?.message === 'string') {
        text = msg.message;
      }"""
    new = """  async function resolveReply(messageId) {
    try {
      const msg = await onebot.getMsg(messageId);
      const senderName = msg?.sender?.card || msg?.sender?.nickname || '';
      // 段落 → 人类可读占位符。原来直接 `[${s.type}]`，会把图片写成 `[image]`，
      // 模型既认不出那是图、也没有可用的 id 去调 get_message_images。
      const segLabel = (s) => {
        const d = s?.data ?? {};
        switch (s?.type) {
          case 'text': return String(d.text ?? '');
          case 'image':
          case 'mface': {
            const sum = String(d.summary ?? '').trim();
            return sum ? `[图片：${sum}]` : '[图片]';
          }
          case 'face': return '[QQ表情]';
          case 'record': return '[语音]';
          case 'video': return '[视频]';
          case 'file': return '[文件]';
          case 'forward': return '[合并转发]';
          case 'reply': return '';          // 引用套引用：只取最外层
          case 'json': return '[卡片]';
          default: return `[${s?.type ?? '未知'}]`;
        }
      };
      let text = '';
      if (Array.isArray(msg?.message)) {
        text = msg.message.map(segLabel).join('').trim();
      } else if (typeof msg?.message === 'string') {
        text = msg.message;
      }"""
    assert old in s, 'app.js 未找到 resolveReply'
    s = s.replace(old, new, 1)

    old_ret = """      return { sender: String(senderName), senderId: String(msg?.sender?.user_id ?? ''), text: String(text).slice(0, 120) };"""
    new_ret = """      // id 一并带回：引用里可能是图片，模型需要它去调 get_message_images
      return {
        sender: String(senderName),
        senderId: String(msg?.sender?.user_id ?? ''),
        text: String(text).slice(0, 120),
        hasMedia: Array.isArray(msg?.message)
          && msg.message.some((x) => ['image', 'mface', 'video', 'record'].includes(x?.type)),
        id: String(messageId)
      };"""
    assert old_ret in s, 'app.js 未找到 resolveReply 返回值'
    s = s.replace(old_ret, new_ret, 1)

    shutil.copy2(P1, P1 + '.bak_replymedia')
    open(P1, 'w', encoding='utf-8').write(s)
    print('app.js: resolveReply 已带图片占位符 + id')

# ---------- 2) onebot.js：引用文本里带上 #id 和行动提示 ----------
P2 = r'F:\QQAI\QQ-agent\src\onebot.js'
t = open(P2, encoding='utf-8').read()

if '引用里的图片' in t:
    print('onebot.js: 已打过补丁')
else:
    old = """              const parts = [];
              if (senderLabel) parts.push(senderLabel);
              if (info.text) parts.push(info.text);
              replyText = `[引用 ${parts.join('：')}]`;"""
    new = """              const parts = [];
              if (senderLabel) parts.push(senderLabel);
              if (info.text) parts.push(info.text);
              // 引用的是图片/表情时，必须给出 id，模型才知道用哪个参数去看
              if (info.hasMedia && info.id) {
                parts.push(`图片 #${info.id}（可用 get_message_images 查看）`);
              }
              replyText = `[引用 ${parts.join('：')}]`;"""
    assert old in t, 'onebot.js 未找到引用构造处'
    t = t.replace(old, new, 1)
    shutil.copy2(P2, P2 + '.bak_replymedia')
    open(P2, 'w', encoding='utf-8').write(t)
    print('onebot.js: 引用文本已带 #id + 提示')
