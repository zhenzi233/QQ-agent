# -*- coding: utf-8 -*-
"""动图拼图改为「按 GIF 时长决定格数」

原来固定 4 帧(2x2)，长动图(7s、12s)只看 4 帧会漏掉大半动作。
现在先 ffprobe 量时长，再按档位选格数：

  ≤1.5s → 4 帧 (2x2)
  ≤3s   → 6 帧 (3x2)
  ≤6s   → 8 帧 (4x2)
  ≤12s  → 12 帧 (4x3)
  >12s  → 16 帧 (4x4)

每格长边按格数收缩(总宽高都控制在 ~960px)，避免长动图的拼图把 token 撑爆。
拼图函数改为返回 { dataUrl, frames, cols, rows, seconds }，调用方据此写说明。
"""
import io
import shutil
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

GIF = r'F:\QQAI\QQ-agent\src\gif-to-video.js'
TOOLS = r'F:\QQAI\QQ-agent\src\tools.js'

# 整体替换旧函数（固定 4 帧）为新实现
OLD_MARK = 'export async function gifContactSheetDataUrl(buffer) {'
NEW_FUNC = '''/**
 * 量 GIF 时长（秒）。失败返回 null —— 调用方按"短动图"处理，不阻塞看图。
 * ffprobe 与 ffmpeg 同目录；没装 ffprobe 时退回 null。
 */
async function probeGifSeconds(file) {
  try {
    const dir = path.dirname(await findFfmpeg() || '');
    const probe = dir ? path.join(dir, process.platform === 'win32' ? 'ffprobe.exe' : 'ffprobe') : 'ffprobe';
    const out = await new Promise((resolve) => {
      const child = spawn(probe, [
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        file
      ]);
      let buf = '';
      child.stdout.on('data', (d) => { buf += d; });
      const timer = setTimeout(() => { try { child.kill(); } catch { /* ignore */ } resolve(''); }, 5000);
      child.on('error', () => { clearTimeout(timer); resolve(''); });
      child.on('close', () => { clearTimeout(timer); resolve(buf); });
    });
    const n = Number(String(out).trim());
    return Number.isFinite(n) && n > 0 ? n : null;
  } catch {
    return null;
  }
}

/**
 * 按时长选格数：越长的动图给越多帧，避免"只看到开头"。
 * 每格长边同步收缩，整张拼图控制在 ~960px 见方，token 与信息量折中。
 */
function sheetPlan(seconds) {
  const s = Number(seconds);
  if (!Number.isFinite(s) || s <= 1.5) return { frames: 4, cols: 2, rows: 2, cell: 360 };
  if (s <= 3) return { frames: 6, cols: 3, rows: 2, cell: 320 };
  if (s <= 6) return { frames: 8, cols: 4, rows: 2, cell: 240 };
  if (s <= 12) return { frames: 12, cols: 4, rows: 3, cell: 240 };
  return { frames: 16, cols: 4, rows: 4, cell: 240 };
}

/**
 * GIF → 帧拼图（单张 PNG），格数随时长变化。返回 { dataUrl, frames, cols, rows, seconds }；
 * 失败（没 ffmpeg / 文件异常）返回 null，调用方退回原样发送。
 */
export async function gifContactSheetDataUrl(buffer) {
  const ffmpeg = await findFfmpeg();
  if (!ffmpeg) return null;
  const stamp = `${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
  const tmpIn = path.join(os.tmpdir(), `qqa_gifsheet_in_${stamp}.gif`);
  const tmpOut = path.join(os.tmpdir(), `qqa_gifsheet_out_${stamp}.png`);
  try {
    fs.writeFileSync(tmpIn, buffer);
    const seconds = await probeGifSeconds(tmpIn);
    const plan = sheetPlan(seconds);
    // fps 由"帧数 / 实际时长"决定：短动图不至于抽到重复帧，长动图能覆盖全程；
    // 时长为空或异常时退回 fps=3（约 1.3 秒取满格数）。
    const fps = seconds && seconds > 0
      ? Math.min(12, Math.max(0.5, plan.frames / seconds))
      : 3;
    const okRun = await runOk(ffmpeg, [
      '-y',
      '-ignore_loop', '0',
      '-t', '30',
      '-i', tmpIn,
      '-vf', `fps=${fps.toFixed(3)},scale='min(${plan.cell},iw)':'min(${plan.cell},ih)':force_original_aspect_ratio=decrease,tile=${plan.cols}x${plan.rows}`,
      '-frames:v', '1',
      '-an',
      tmpOut
    ], 30000);
    if (!okRun || !fs.existsSync(tmpOut)) return null;
    const out = fs.readFileSync(tmpOut);
    if (!out.length || out.length > 8 * 1024 * 1024) return null;
    return {
      dataUrl: `data:image/png;base64,${out.toString('base64')}`,
      frames: plan.frames,
      cols: plan.cols,
      rows: plan.rows,
      seconds: seconds || null
    };
  } catch {
    return null;
  } finally {
    try { if (fs.existsSync(tmpIn)) fs.unlinkSync(tmpIn); } catch { /* ignore */ }
    try { if (fs.existsSync(tmpOut)) fs.unlinkSync(tmpOut); } catch { /* ignore */ }
  }
}
'''

s = open(GIF, encoding='utf-8').read()
idx = s.find(OLD_MARK)
assert idx > 0, 'gif-to-video.js 未找到旧拼图函数'
shutil.copy2(GIF, GIF + '.bak_sheetdur')
s = s[:idx] + NEW_FUNC
open(GIF, 'w', encoding='utf-8').write(s)
print('gif-to-video.js: 拼图已改为按时长选格数')

# tools.js：新返回值是对象，且补图文案带上帧数/时长
t = open(TOOLS, encoding='utf-8').read()
old_use = """    const sheet = await gifContactSheetDataUrl(buffer);
    if (sheet) {
      return {
        dataUrl: sheet,
        isGif: false,
        gifSheet: { frames: 4 },
        gifBuffer: buffer
      };
    }"""
new_use = """    const sheet = await gifContactSheetDataUrl(buffer);
    if (sheet) {
      return {
        dataUrl: sheet.dataUrl,
        isGif: false,
        gifSheet: { frames: sheet.frames, cols: sheet.cols, rows: sheet.rows, seconds: sheet.seconds },
        gifBuffer: buffer
      };
    }"""
assert old_use in t, 'tools.js 未找到拼图调用处'
t = t.replace(old_use, new_use, 1)
open(TOOLS, 'w', encoding='utf-8').write(t)
print('tools.js: 已适配新的返回值')
