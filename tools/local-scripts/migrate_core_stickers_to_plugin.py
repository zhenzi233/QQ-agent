# -*- coding: utf-8 -*-
"""把核心表情库（data/stickers.json）导入 sticker-steal 插件的本地库

为什么需要：核心表情系统已关闭，新插件自建库是空的（0 张），要靠群友慢慢喂。
这个脚本把核心那 300+ 张（含描述/标签/使用次数）一次性搬过去，按内容 sha1 去重。

插件的数据格式（见 skills/re-sticker-steal/index.js）：
  data/sticker-steal/index.json   { version:1, bornAt, items:[...], ... }
  data/sticker-steal/images/<sha1前16位>.<ext>
  条目关键字段：src(sha1 全值) / file(图片文件名) / ext / bytes / note(备注=描述)
               / tags / source / createdAt / useCount / sentCount / animated
"""
import hashlib
import io
import json
import os
import shutil
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

QA = Path(r'F:\QQAI\QQ-agent')
CORE = QA / 'data' / 'stickers.json'
PLUGIN_DIR = QA / 'data' / 'sticker-steal'
IMG_DIR = PLUGIN_DIR / 'images'
INDEX = PLUGIN_DIR / 'index.json'

MAX_ITEM_MB = 6.0      # 插件默认单张上限
MAX_LIB = 800          # 插件默认库上限


def sniff(buf: bytes) -> str:
    if buf[:8] == b'\x89PNG\r\n\x1a\n':
        return 'png'
    if buf[:3] == b'\xff\xd8\xff':
        return 'jpg'
    if buf[:3] == b'GIF':
        return 'gif'
    if buf[:4] == b'RIFF' and buf[8:12] == b'WEBP':
        return 'webp'
    if buf[:2] == b'BM':
        return 'bmp'
    return ''


def read_local(entry: dict):
    """优先读 localFile（file:///...），否则跳过。"""
    local = str(entry.get('localFile') or '')
    if not local.startswith('file:///'):
        return None
    path = unquote(urlparse(local).path)
    if path.startswith('/') and len(path) > 2 and path[2] == ':':
        path = path[1:]           # /F:/... → F:/...
    p = Path(path)
    if not p.is_file():
        return None
    return p.read_bytes()


def clean_name(name: str) -> str:
    """核心条目 id 里带 QQ 号/冒号，插件的 key 只用 src/file，这里只用来做备注兜底。"""
    return str(name or '').strip()


def main():
    core = json.load(open(CORE, encoding='utf-8'))
    IMG_DIR.mkdir(parents=True, exist_ok=True)

    # 已有库（如果之前跑过）——按 src 合并，不重复
    existing = {'items': []}
    if INDEX.is_file():
        try:
            existing = json.load(open(INDEX, encoding='utf-8'))
        except Exception:
            existing = {'items': []}
    items = [it for it in (existing.get('items') or []) if isinstance(it, dict)]
    by_src = {str(it.get('src') or ''): it for it in items if it.get('src')}

    stats = {'added': 0, 'dup': 0, 'noFile': 0, 'tooBig': 0, 'badFormat': 0, 'overLimit': 0}
    now_ms = int(time.time() * 1000)

    for entry in core:
        buf = read_local(entry)
        if not buf:
            stats['noFile'] += 1
            continue
        src = hashlib.sha1(buf).hexdigest()
        if src in by_src:
            stats['dup'] += 1
            continue
        if len(items) >= MAX_LIB:
            stats['overLimit'] += 1
            continue
        ext = sniff(buf)
        if not ext:
            stats['badFormat'] += 1
            continue
        size_mb = len(buf) / 1048576
        if size_mb > MAX_ITEM_MB:
            stats['tooBig'] += 1
            continue

        fname = f'{src[:16]}.{ext}'
        target = IMG_DIR / fname
        if not target.is_file():
            target.write_bytes(buf)

        note = clean_name(entry.get('localNote')) or clean_name(entry.get('desc'))
        tags = [str(t).strip() for t in (entry.get('tags') or []) if str(t).strip()][:8]
        created = now_ms
        raw_created = str(entry.get('createdAt') or '')
        if raw_created:
            try:
                created = int(time.mktime(time.strptime(raw_created[:19], '%Y-%m-%dT%H:%M:%S')) * 1000)
            except Exception:
                pass

        item = {
            'key': f'src:{src}',
            'src': src,
            'file': fname,
            'path': '',
            'bytes': len(buf),
            'ext': ext,
            'tags': tags,
            'note': note[:120] if note else '',
            'text': '',
            'source': 'observed',
            'chatKey': '',
            'chatName': '导入自核心库',
            'createdAt': created,
            'usedAt': 0,
            'useCount': max(0, int(entry.get('useCount') or 0)),
            'sentCount': 0,
            'sources': ['core-import'],
            'animated': ext == 'gif',
        }
        item["path"] = str(target)
        items.append(item)
        by_src[src] = item
        stats['added'] += 1

    lib = {
        'version': 1,
        'bornAt': int(existing.get('bornAt') or now_ms),
        'items': items,
        'lastSendAt': existing.get('lastSendAt', 0),
        'lastGlobalSendAt': existing.get('lastGlobalSendAt', 0),
        'sentDay': existing.get('sentDay', ''),
        'sentToday': existing.get('sentToday', 0),
        'sentTotal': existing.get('sentTotal', 0),
        'lastBaseRewardAt': existing.get('lastBaseRewardAt', 0),
        'chatStats': existing.get('chatStats', {}),
        'counters': {
            'collected': len(items), 'duplicates': stats['dup'], 'skipped': 0,
            'evicted': 0, 'failed': stats['noFile'] + stats['badFormat'], 'sent': 0,
            'quips': 0, 'lookFailed': 0, 'freqBlocked': 0,
        },
    }
    if INDEX.is_file():
        shutil.copy2(INDEX, str(INDEX) + '.bak_beforeimport')
    INDEX.write_text(json.dumps(lib, ensure_ascii=False, indent=1), encoding='utf-8')

    print('导入完成：库内 %d 张' % len(items))
    for k, v in stats.items():
        print('  %-10s %d' % (k, v))
    print('图片目录: %s（文件 %d 个）' % (IMG_DIR, len(list(IMG_DIR.glob('*')))))
    print('索引: %s' % INDEX)


if __name__ == '__main__':
    main()
