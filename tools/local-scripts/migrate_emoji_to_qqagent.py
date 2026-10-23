# -*- coding: utf-8 -*-
"""把 MaiBot2 的表情库(327 张 + 描述)迁移到 QQ-agent 的 stickers.json + sticker-images

QQ-agent 的表情条目格式见 src/stickers.js:normalizeStickerEntry。
发送时优先用 localFile(file:///...),所以只要把文件和条目写对就能直接用。
"""
import hashlib
import io
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SRC_DB = r'F:\QQAI\MaiBot2\data\MaiBot.db'
SRC_EMOJI = r'F:\QQAI\MaiBot2\data\emoji'
QA = r'F:\QQAI\QQ-agent'
STORE = os.path.join(QA, 'data', 'stickers.json')
IMGDIR = os.path.join(QA, 'data', 'sticker-images')

os.makedirs(IMGDIR, exist_ok=True)

store = json.load(open(STORE, encoding='utf-8')) if os.path.exists(STORE) else []
print('QQ-agent 现有表情:', len(store))
existing_md5 = {str(e.get('md5') or '').upper() for e in store if e.get('md5')}
existing_id = {str(e.get('id') or '') for e in store}

con = sqlite3.connect('file:%s?mode=ro' % SRC_DB, uri=True)
rows = con.execute("""SELECT full_path, description, image_hash FROM images
                      WHERE image_type='EMOJI' AND full_path IS NOT NULL""").fetchall()
print('MaiBot2 表情记录:', len(rows))

now = datetime.now().isoformat()
added = skipped = missing = 0

for full_path, desc, emoji_hash in rows:
    if not full_path or not os.path.isfile(full_path):
        missing += 1
        continue
    data = open(full_path, 'rb').read()
    md5 = hashlib.md5(data).hexdigest().upper()
    if md5 in existing_md5:
        skipped += 1
        continue

    ext = os.path.splitext(full_path)[1].lower() or '.png'
    sid = 'mai_%s' % md5[:20]
    if sid in existing_id:
        skipped += 1
        continue
    dest = os.path.join(IMGDIR, sid + ext)
    open(dest, 'wb').write(data)
    uri = 'file:///' + dest.replace('\\', '/')

    text = str(desc or '').strip()
    store.append({
        'id': sid,
        'resId': sid,
        'emojiId': '',
        'qqFile': '',
        'localFile': uri,
        'persistFailed': False,
        'url': uri,
        'md5': md5,
        'desc': text[:20],
        'localNote': text[:200],
        'tags': [],
        'usage': '',
        'source': 'manual',
        'useCount': 0,
        'lastUsedAt': 0,
        'lastContext': '',
        'createdAt': now,
        'updatedAt': now,
    })
    existing_md5.add(md5)
    existing_id.add(sid)
    added += 1

json.dump(store, open(STORE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('新增 %d 条 | 已存在跳过 %d | 源文件缺失 %d' % (added, skipped, missing))
print('QQ-agent 表情总数:', len(store))
print('本地图片数:', len(os.listdir(IMGDIR)))
