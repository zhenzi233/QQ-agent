# -*- coding: utf-8 -*-
"""表情包支持「分群设置」—— 后端：配置层 + 提示词/快照按群取值

结构对齐「活跃设置」：`sticker.unifiedSticker`（统一开关）+ `sticker.groupOverrides[群号]`。
统一模式（默认）行为与原来完全一致；关掉统一后按群合并覆盖，字段缺失回落全局。
"""
import io
import shutil
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ---------- 1. config.js：默认值 + 解析函数 ----------
P1 = r'F:\QQAI\QQ-agent\src\config.js'
s = open(P1, encoding='utf-8').read()

if 'stickerConfigForChat' in s:
    print('config.js: 已打过补丁')
else:
    old_sticker = """  sticker: {
    enabled: true,
    promptMaxStickers: 10,
    collectEnabled: true,
    maxCollectPerHour: 10,"""
    new_sticker = """  sticker: {
    enabled: true,
    promptMaxStickers: 10,
    collectEnabled: true,
    maxCollectPerHour: 10,
    // 分群设置：true = 所有群共用上面这几个值；false = 按下表按群覆盖
    unifiedSticker: true,
    // 按群覆盖：{ "群号": { enabled, encourage, promptMaxStickers } }，缺省字段回落全局
    groupOverrides: {},"""
    assert old_sticker in s, 'config.js 未找到 sticker 默认值'
    s = s.replace(old_sticker, new_sticker, 1)

    FUNC = '''
/**
 * 取某个会话实际生效的表情包配置。
 *
 * unifiedSticker !== false（默认）→ 直接用全局；
 * 分群模式 → 合并 groupOverrides[群号]（只允许覆盖 enabled / encourage / promptMaxStickers，
 * 其余字段如 collectEnabled 属于"收藏"这个全局动作，不按群走）。
 *
 * 与 storeConfigForChat 一样接受 chatKey（group:123 / private:456），
 * 也兼容只传群号的写法（群覆盖表按群号建键）。
 */
export function stickerConfigForChat(chatKey) {
  const sticker = getConfig().sticker || {};
  if (sticker.unifiedSticker !== false) return sticker;
  const raw = String(chatKey || '');
  const id = raw.includes(':') ? raw.split(':').slice(1).join(':') : raw;
  const overrides = sticker.groupOverrides || {};
  const patch = overrides[id] || overrides[raw];
  if (!patch || typeof patch !== 'object') return sticker;
  const out = { ...sticker };
  if (patch.enabled === true || patch.enabled === false) out.enabled = patch.enabled;
  const lvl = Number(patch.encourage);
  if (Number.isFinite(lvl)) out.encourage = Math.min(3, Math.max(0, lvl));
  const max = Number(patch.promptMaxStickers);
  if (Number.isFinite(max) && max > 0) out.promptMaxStickers = Math.min(50, Math.max(1, max));
  return out;
}

'''
    anchor = 'export function storeConfigForChat(chatKey) {'
    assert anchor in s, 'config.js 未找到 storeConfigForChat'
    s = s.replace(anchor, FUNC.lstrip('\n') + anchor, 1)
    shutil.copy2(P1, P1 + '.bak_stkper')
    open(P1, 'w', encoding='utf-8').write(s)
    print('config.js: 已加 unifiedSticker / groupOverrides / stickerConfigForChat')

# ---------- 2. prompt.js：按群取表情配置 ----------
P2 = r'F:\QQAI\QQ-agent\src\prompt.js'
t = open(P2, encoding='utf-8').read()

if 'stickerConfigForChat' in t:
    print('prompt.js: 已打过补丁')
else:
    old_rules = """function stickerRules() {
  // 活跃度档位直接改写策略段的频率行（引导统一在系统提示，不在"本次输入"重复）
  const lvl = Math.min(3, Math.max(0, Number(getConfig().sticker?.encourage) || 0));"""
    new_rules = """function stickerRules(chatKey = '') {
  // 活跃度档位直接改写策略段的频率行（引导统一在系统提示，不在"本次输入"重复）
  // 分群设置：走 stickerConfigForChat，统一模式下等价于全局值。
  const lvl = Math.min(3, Math.max(0, Number(stickerConfigForChat(chatKey)?.encourage) || 0));"""
    assert old_rules in t, 'prompt.js 未找到 stickerRules'
    t = t.replace(old_rules, new_rules, 1)

    # 调用点：stickerRules() → stickerRules(cfg.chatKey?) 在 buildSystemPrompt 内
    assert '    stickerRules(),' in t, 'prompt.js 未找到 stickerRules 调用'
    t = t.replace('    stickerRules(),', '    stickerRules(chatKeyForSticker),', 1)

    # buildSystemPrompt 里算出 chatKeyForSticker
    old_head = """export function buildSystemPrompt({ persona, skillContext, extraSections = [] } = {}) {
  const cfg = persona ?? getConfig().persona;"""
    new_head = """export function buildSystemPrompt({ persona, skillContext, extraSections = [] } = {}) {
  const cfg = persona ?? getConfig().persona;
  // 表情包分群设置要用会话标识；取不到就退回全局（'' 在统一模式下等价）
  const chatKeyForSticker = String(skillContext?.chatKey || skillContext?.streamId || '');"""
    assert old_head in t, 'prompt.js 未找到 buildSystemPrompt 头'
    t = t.replace(old_head, new_head, 1)

    # 表情库列举：按群取 promptMaxStickers / enabled
    old_list = """  if (cfg.sticker?.enabled !== false) {
    const stickerCtx = buildStickerContext(ctx.stickerEntries || [], Number(cfg.sticker?.promptMaxStickers) || 10);"""
    new_list = """  const stickerCfg = stickerConfigForChat(chatKeyForSticker);
  if (stickerCfg.enabled !== false) {
    const stickerCtx = buildStickerContext(ctx.stickerEntries || [], Number(stickerCfg.promptMaxStickers) || 10);"""
    assert old_list in t, 'prompt.js 未找到表情库列举段'
    t = t.replace(old_list, new_list, 1)

    # 补 import
    import_line = "import { getConfig } from './config.js';"
    if import_line in t and 'stickerConfigForChat' not in t.split('export')[0]:
        t = t.replace(import_line, "import { getConfig, stickerConfigForChat } from './config.js';", 1)
    elif import_line not in t:
        # 兼容别的导入写法
        t = "import { stickerConfigForChat } from './config.js';\n" + t

    shutil.copy2(P2, P2 + '.bak_stkper')
    open(P2, 'w', encoding='utf-8').write(t)
    print('prompt.js: 已改为按群取表情配置')

# ---------- 3. orchestrator.js：表情快照按群判断 ----------
P3 = r'F:\QQAI\QQ-agent\src\orchestrator.js'
o = open(P3, encoding='utf-8').read()
if 'stickerConfigForChat' in o:
    print('orchestrator.js: 已打过补丁')
else:
    old = """    let stickerEntries = [];
    if (cfg.sticker?.enabled !== false) {"""
    new = """    let stickerEntries = [];
    if (stickerConfigForChat(chatKey).enabled !== false) {"""
    assert old in o, 'orchestrator.js 未找到表情快照段'
    o = o.replace(old, new, 1)
    imp = "import { getConfig, updateConfig, ROOT, DATA_DIR } from './config.js';"
    if imp in o:
        o = o.replace(imp, "import { getConfig, updateConfig, ROOT, DATA_DIR, stickerConfigForChat } from './config.js';", 1)
    shutil.copy2(P3, P3 + '.bak_stkper')
    open(P3, 'w', encoding='utf-8').write(o)
    print('orchestrator.js: 表情快照改为按群判断')
