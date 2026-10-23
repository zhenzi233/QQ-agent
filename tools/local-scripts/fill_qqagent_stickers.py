# -*- coding: utf-8 -*-
"""补齐 QQ-agent 表情条目的描述与本地文件(针对 md5 已存在但 desc/localFile 为空的条目)"""
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
STORE = r'F:\QQAI\QQ-agent\data\stickers.json'
IMGDIR = r'F:\QQAI\QQ-agent\data\sticker-images'
SEP = chr(92)  # 反斜杠

store = json.load(open(STORE, encoding='utf-8'))
by_md5 = {str(e.get('md5') or '').upper(): e for e in store if e.get('md5')}

con = sqlite3.connect('file:%s?mode=ro' % SRC_DB, uri=True)
rows = con.execute("""SELECT full_path, description FROM images
                      WHERE image_type='EMOJI' AND full_path IS NOT NULL""").fetchall()

filled = 0
for full_path, desc in rows:
    if not full_path or not os.path.isfile(full_path):
        continue
    data = open(full_path, 'rb').read()
    md5 = hashlib.md5(data).hexdigest().upper()
    e = by_md5.get(md5)
    if not e:
        continue
    text = str(desc or '').strip()
    changed = False
    if text and not e.get('desc'):
        e['desc'] = text[:20]
        changed = True
    if text and not e.get('localNote'):
        e['localNote'] = text[:200]
        changed = True
    if not str(e.get('localFile') or '').startswith('file:///'):
        ext = os.path.splitext(full_path)[1] or '.png'
        dest = os.path.join(IMGDIR, str(e['id']) + ext)
        shutil.copy2(full_path, dest)
        uri = 'file:///' + dest.replace(SEP, '/')
        e['localFile'] = uri
        e['url'] = uri
        e['persistFailed'] = False
        changed = True
    if changed:
        e['updatedAt'] = datetime.now().isoformat()
        filled += 1

json.dump(store, open(STORE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('补齐条目:', filled)
print('总数:', len(store))
print('有描述:', sum(1 for e in store if e.get('desc')))
print('有本地文件:', sum(1 for e in store if str(e.get('localFile') or '').startswith('file:///')))
print('本地图片数:', len(os.listdir(IMGDIR)))
