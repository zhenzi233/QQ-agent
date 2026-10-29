// 给 QQ 新图床（multimedia.nt.qq.com.cn）的 URL 补 rkey。
//
// ── 为什么需要 ─────────────────────────────────────────────────────────────
// QQ 现在给群里图片的 URL 形如：
//   https://multimedia.nt.qq.com.cn/download?appid=1407&fileid=...&spec=0
// **不带 rkey 时一律 400 invalid rkey**。老的 gchat.qpic.cn 链接不需要签名，
// 所以「有些图能看、有些图看不到」，看起来像随机故障。
//
// 实测：把 SnowLuma 的 `get_rkey` 返回里 **type=20** 的那条拼到 URL 末尾，
// 同一张图立刻 200。type=10 那条对群图无效（对私聊图多半相反）。
//
// SnowLuma 自己下载同一张图也是 400（它没把 rkey 拼上），所以这一层补丁放在
// 客户端侧：拿到 URL 之后、真正 fetch 之前签一次。

/** 需要 rkey 的图床域名。 */
const RKEY_HOSTS = ['multimedia.nt.qq.com.cn'];

/** 这条 URL 是否已经带签名 / 是否需要签名。 */
export function needsRKey(rawUrl) {
  const url = String(rawUrl || '').trim();
  if (!/^https?:\/\//i.test(url)) return false;
  let host = '';
  try { host = new URL(url).hostname.toLowerCase(); } catch { return false; }
  if (!RKEY_HOSTS.some((h) => host === h || host.endsWith(`.${h}`))) return false;
  return !/[?&]rkey=/.test(url);
}

/** 把 rkey（形如 `&rkey=CAQ...`）拼到 URL 上，已有参数就接 &，没有就 ?。 */
export function withRKey(rawUrl, rkey) {
  const url = String(rawUrl || '').trim();
  const key = String(rkey || '').trim();
  if (!url || !key) return url;
  if (/[?&]rkey=/.test(url)) return url;
  const suffix = key.replace(/^[?&]/, '');
  return `${url}${url.includes('?') ? '&' : '?'}${suffix}`;
}

/**
 * 从 `get_rkey` 的返回里挑一条。
 * type=20 用于群聊图片，type=10 用于私聊 —— 拿不准时先给的优先，另一条留作重试。
 */
export function pickRKey(list, { isGroup = true } = {}) {
  const arr = Array.isArray(list) ? list : (Array.isArray(list?.data) ? list.data : []);
  const wanted = isGroup ? 20 : 10;
  const other = isGroup ? 10 : 20;
  const norm = (x) => ({
    rkey: String(x?.rkey ?? '').trim(),
    type: Number(x?.type),
    ttl: Number(x?.ttl) || 0,
    createTime: Number(x?.create_time) || 0
  });
  const items = arr.map(norm).filter((x) => x.rkey);
  const first = items.find((x) => x.type === wanted) || items.find((x) => x.type === other) || items[0] || null;
  const second = items.find((x) => x !== first && x.rkey) || null;
  return { primary: first, alternate: second };
}
