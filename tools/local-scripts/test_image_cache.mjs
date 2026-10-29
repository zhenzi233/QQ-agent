// 冒烟测试：图片本地化（image-cache）
// 用真实的失败 URL（multimedia 图床、不带 rkey）走一遍 localizeMessage：
// 拿 rkey 走 HTTP 3101（SnowLuma），下载、落盘、索引、按 mid 反查。
import fs from 'node:fs';
import path from 'node:path';

const DATA = 'F:/QQAI/QQ-agent/data';
process.env.QQ_AGENT_DATA_DIR = DATA;

const { localizeMessage, findLocalByMid, imageCacheStats, pruneImages } = await import('file:///F:/QQAI/QQ-agent/src/image-cache.js');

const TOKEN = 'St8tVLuU63SPcvTCsokd2wEsYIJgTkdSMWM_YziLPLI';
const onebot = {
  async call(action, params) {
    if (action !== 'get_rkey') throw new Error(`未实现 ${action}`);
    const res = await fetch('http://127.0.0.1:3101/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${TOKEN}` },
      body: JSON.stringify({ action, params }),
    });
    const json = await res.json();
    return json.data;
  },
};

// 从消息存档里挑一张 multimedia 图床的图（不带 rkey 的那种）
const files = fs.readdirSync(path.join(DATA, 'messages')).filter((f) => f.endsWith('.json'));
let target = null;
for (const f of files) {
  const d = JSON.parse(fs.readFileSync(path.join(DATA, 'messages', f), 'utf8'));
  for (const e of (d.messages || []).slice(-300)) {
    for (const m of (e.media || [])) {
      if (m.kind === 'image' && String(m.url || '').includes('multimedia.nt.qq.com.cn') && !/rkey=/.test(String(m.url))) {
        target = { mid: e.mid, chatKey: d.chatKey, media: [m] };
      }
    }
  }
  if (target) break;
}
if (!target) { console.log('没找到目标图片'); process.exit(1); }
console.log('目标 mid=%s chatKey=%s', target.mid, target.chatKey);
console.log('URL 尾部:', String(target.media[0].url).slice(-46));

const n = await localizeMessage({ onebot, ...target });
console.log('保存张数:', n);
const hit = findLocalByMid(target.mid);
console.log('按 mid 反查:', hit || '(空)');
if (hit) {
  const st = fs.statSync(hit);
  console.log('文件大小: %d 字节, 头部: %s', st.size, fs.readFileSync(hit).slice(0, 4).toString('hex'));
}
console.log('缓存统计:', JSON.stringify(imageCacheStats()));
console.log('清理:', pruneImages(), '张');
