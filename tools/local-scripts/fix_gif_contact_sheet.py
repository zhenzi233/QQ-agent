# -*- coding: utf-8 -*-
"""给「模型只能看图、看不了动图」的情况补一张帧拼图

现状：只开图片输入(api.video=false)时，GIF 按原图发给模型。网关不报错、
但只解码第一帧——模型只会说"只拿到第一帧"，完全看不到后半段动作。

做法：GIF 进来时先用 ffmpeg 抽 4 帧拼成 2x2 一张 PNG，连同说明一起发给模型。
单张图、token 成本可控，又能看到动作走向；拼图失败则退回原样发送（原有降级不受影响）。
"""
import io
import shutil
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

GIF = r'F:\QQAI\QQ-agent\src\gif-to-video.js'
TOOLS = r'F:\QQAI\QQ-agent\src\tools.js'

FUNC = '''
/**
 * GIF → 2x2 帧拼图（单张 PNG）。
 *
 * 用途：模型只支持图片输入（api.video 关闭）时，直接发 GIF 往往只被解码第一帧，
 * 模型只能说「只拿到第一帧」。这里把 4 帧按时间顺序拼成一张图，动作走向就看得见了。
 * 失败（没 ffmpeg / 文件异常）返回 null，调用方退回原样发送，不影响既有降级路径。
 */
export async function gifContactSheetDataUrl(buffer) {
  const ffmpeg = await findFfmpeg();
  if (!ffmpeg) return null;
  const stamp = `${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
  const tmpIn = path.join(os.tmpdir(), `qqa_gif4_in_${stamp}.gif`);
  const tmpOut = path.join(os.tmpdir(), `qqa_gif4_out_${stamp}.png`);
  try {
    fs.writeFileSync(tmpIn, buffer);
    // fps=3 + tile=2x2：约 1.3 秒内均匀取 4 帧；-t 4 兜住超长 GIF
    // 每格长边压到 360px，拼完 ≈720px，token 与清晰度折中。
    const okRun = await runOk(ffmpeg, [
      '-y',
      '-ignore_loop', '0',
      '-t', '4',
      '-i', tmpIn,
      '-vf', "fps=3,scale='min(360,iw)':'min(360,ih)':force_original_aspect_ratio=decrease,tile=2x2",
      '-frames:v', '1',
      '-an',
      tmpOut
    ], 25000);
    if (!okRun || !fs.existsSync(tmpOut)) return null;
    const out = fs.readFileSync(tmpOut);
    if (!out.length || out.length > 6 * 1024 * 1024) return null;
    return `data:image/png;base64,${out.toString('base64')}`;
  } catch {
    return null;
  } finally {
    try { if (fs.existsSync(tmpIn)) fs.unlinkSync(tmpIn); } catch { /* ignore */ }
    try { if (fs.existsSync(tmpOut)) fs.unlinkSync(tmpOut); } catch { /* ignore */ }
  }
}
'''

s = open(GIF, encoding='utf-8').read()
if 'gifContactSheetDataUrl' in s:
    print('gif-to-video.js 已有拼图函数')
else:
    shutil.copy2(GIF, GIF + '.bak_sheet')
    s = s.rstrip() + '\n' + FUNC
    open(GIF, 'w', encoding='utf-8').write(s)
    print('gif-to-video.js: 已加帧拼图函数')

t = open(TOOLS, encoding='utf-8').read()
if 'gifContactSheetDataUrl' in t:
    print('tools.js 已接入')
else:
    shutil.copy2(TOOLS, TOOLS + '.bak_sheet')
    # 1) 引入
    old_imp = "import { isGifBuffer, gifToVideoDataUrl, resolveGifRoute } from './gif-to-video.js';"
    new_imp = ("import { isGifBuffer, gifToVideoDataUrl, resolveGifRoute, "
               "gifContactSheetDataUrl } from './gif-to-video.js';")
    assert old_imp in t, 'tools.js 未找到 gif-to-video 引用'
    t = t.replace(old_imp, new_imp, 1)

    # 2) 在 GIF 分岔里插入「拼图」优先路径
    old_branch = """  if (isGifBuffer(buffer) && currentGifRoute() === 'video') {"""
    new_branch = """  // 只开图片输入时：先尝试把 GIF 拼成 4 帧一张图（否则多数模型只解码第一帧）
  if (isGifBuffer(buffer) && currentGifRoute() !== 'video') {
    const sheet = await gifContactSheetDataUrl(buffer);
    if (sheet) {
      return {
        dataUrl: sheet,
        isGif: false,
        gifSheet: { frames: 4 },
        gifBuffer: buffer
      };
    }
  }
  if (isGifBuffer(buffer) && currentGifRoute() === 'video') {"""
    assert old_branch in t, 'tools.js 未找到 GIF 分岔'
    t = t.replace(old_branch, new_branch, 1)
    open(TOOLS, 'w', encoding='utf-8').write(t)
    print('tools.js: 已接入帧拼图（优先于原样发送）')
