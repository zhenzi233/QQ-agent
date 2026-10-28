# -*- coding: utf-8 -*-
"""引用里的图片真能看 —— 修「引用的那张图打不开」第二轮

第一轮只让模型拿到了 id；这一轮解决「拿到 id 也读不出图」的三种情况：

  ① 被引用的消息不在本会话存档里（自己发的消息、太老的消息）→ findByMid 直接失败
  ② 图片段落只给 `url` 不给 `file`，而 url 指向的是**目录**（本地表情库发的图就是这样）
  ③ 本地文件（file:///...）走网络下载当然失败

改法：
  · 存档里找不到 → 用 onebot.getMsg(messageId) 拿原始段落，从段落里提 image/mface
  · 每个候选同时带上 url 和 file；本地文件（file:///、盘符路径、或 url 是目录+file）直接读盘
  · 全部失败时给出可执行的提示，而不是一句「获取失败」
"""
import io
import shutil
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

P = r'F:\QQAI\QQ-agent\src\tools.js'
s = open(P, encoding='utf-8').read()

if 'resolveLocalImageFile' in s:
    print('tools.js: 已打过补丁')
    raise SystemExit

# ---------- 1) 新增两个本地文件助手（插在 downloadImageAsDataUrl 之前） ----------
HELPERS = '''/**
 * 把「url + file」解析成本机上一个真实存在的图片文件路径。
 * 兼容三种脏数据（都是实测遇到的）：
 *   file:///F:/dir            ← url 是目录，真正的文件名在 file 里
 *   file:///F:/dir/x.png      ← 正常本地文件
 *   F:/dir/x.png / C:\\dir\\x.png
 * 解析不出就返回空串（交给网络下载路径）。
 */
function resolveLocalImageFile(url, file = '') {
  const raw = String(url || '').trim();
  const name = String(file || '').trim();
  const unescape = (p) => {
    let out = p;
    try { out = decodeURIComponent(p); } catch { /* 保留原样 */ }
    return out.replace(/^\\/([A-Za-z]:[\\\\/])/, '$1');   // /F:/x → F:/x
  };
  const candidates = [];
  if (/^file:\\/\\//i.test(raw)) {
    const p = unescape(raw.replace(/^file:\\/\\/\\/?/i, ''));
    candidates.push(p);
    if (name) candidates.push(require('path').join(p, name.replace(/^.*[\\\\/]/, '')));
  } else if (/^[A-Za-z]:[\\\\/]/.test(raw)) {
    candidates.push(raw);
    if (name) candidates.push(require('path').join(raw, name.replace(/^.*[\\\\/]/, '')));
  }
  for (const c of candidates) {
    try {
      if (c && require('fs').statSync(c).isFile()) return c;
    } catch { /* 下一个 */ }
  }
  return '';
}

/** 本机图片文件 → dataURL（按文件头判断 mime，不信任扩展名）。 */
function localImageToDataUrl(filePath) {
  const buf = require('fs').readFileSync(filePath);
  if (!buf || !buf.length) throw new Error('本地图片为空');
  let mime = 'image/png';
  if (buf[0] === 0xff && buf[1] === 0xd8) mime = 'image/jpeg';
  else if (buf.slice(0, 3).toString('latin1') === 'GIF') mime = 'image/gif';
  else if (buf.slice(0, 4).toString('latin1') === 'RIFF' && buf.slice(8, 12).toString('latin1') === 'WEBP') mime = 'image/webp';
  else if (buf[0] === 0x42 && buf[1] === 0x4d) mime = 'image/bmp';
  return { dataUrl: `data:${mime};base64,${buf.toString('base64')}`, gifBuffer: mime === 'image/gif' ? buf : null };
}

'''

anchor = 'async function downloadImageAsDataUrl(url, timeoutMs = 30000) {'
assert anchor in s, '未找到 downloadImageAsDataUrl'
s = s.replace(anchor, HELPERS + anchor, 1)

# ---------- 2) get_message_images：存档里没有就用 onebot.getMsg 兜底 ----------
old = """        const entry = ctx.store.findByMid(ctx.chatKey, args.messageId);
        if (!entry) return err(`当前会话找不到消息 ${args.messageId}。${midHint(ctx)}`);
        const allUrls = (entry.media || []).filter((m) => m.kind === 'image' && m.url).map((m) => m.url);
        if (!allUrls.length) return ok(`消息 ${args.messageId} 没有可查看的图片`);"""
new = """        const entry = ctx.store.findByMid(ctx.chatKey, args.messageId);
        // 取媒体清单：优先本会话存档，存档里没有（自己发的/太老/来自引用）就用协议端取原始段落
        let mediaList = entry
          ? (entry.media || []).filter((m) => m.kind === 'image' && (m.url || m.file))
          : [];
        if (!mediaList.length && ctx.onebot?.getMsg) {
          try {
            const raw = await ctx.onebot.getMsg(String(args.messageId));
            const segs = Array.isArray(raw?.message) ? raw.message : [];
            mediaList = segs
              .filter((seg) => ['image', 'mface'].includes(seg?.type))
              .map((seg) => ({ kind: 'image', url: String(seg?.data?.url ?? ''), file: String(seg?.data?.file ?? '') }))
              .filter((m) => m.url || m.file);
          } catch { /* 协议端也取不到就走下面的错误提示 */ }
        }
        if (!mediaList.length) {
          return err(`消息 ${args.messageId} 里没找到可看的图片（存档和协议端都没有）。如果那是引用的图，先确认引用里带了 #id；也可以用 get_recent_messages 找到带图的那条。`);
        }
        const allUrls = mediaList;"""
assert old in s, '未找到 get_message_images 取媒体段'
s = s.replace(old, new, 1)

# 分页与下载：改成对 {url,file} 处理，本地文件直接读盘
old2 = """        const urls = allUrls.slice(offset, offset + limit);
        if (!urls.length) {
          return ok(`消息 ${args.messageId} 共 ${allUrls.length} 张图，offset=${offset} 已经超出范围`);
        }
        const results = [];
        const failed = [];
        for (const url of urls) {
          try { results.push(await downloadImageAsDataUrl(url)); } catch (e) { failed.push(String(e?.message ?? e)); }
        }"""
new2 = """        const urls = allUrls.slice(offset, offset + limit);
        if (!urls.length) {
          return ok(`消息 ${args.messageId} 共 ${allUrls.length} 张图，offset=${offset} 已经超出范围`);
        }
        const results = [];
        const failed = [];
        for (const media of urls) {
          const local = resolveLocalImageFile(media.url, media.file);
          if (local) {
            // 本地表情库/本机图片：不下载，直接读盘（走网络必然失败）
            try { results.push(localImageToDataUrl(local)); } catch (e) { failed.push(String(e?.message ?? e)); }
            continue;
          }
          try { results.push(await downloadImageAsDataUrl(media.url)); } catch (e) { failed.push(String(e?.message ?? e)); }
        }"""
assert old2 in s, '未找到分页/下载段'
s = s.replace(old2, new2, 1)

shutil.copy2(P, P + '.bak_quotedimg')
open(P, 'w', encoding='utf-8').write(s)
print('tools.js: 已加本地读盘 + onebot.getMsg 兜底')
