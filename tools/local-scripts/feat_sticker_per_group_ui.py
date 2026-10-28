# -*- coding: utf-8 -*-
"""表情包分群设置 —— UI：卡头统一开关 + 群选择 + 单群编辑

交互刻意与「活跃设置」一致：统一开关在卡头，关掉后出现群按钮；改哪个群即时保存
（与聊天设置其它字段同一套自动保存链），不引入额外的「保存/取消」草稿态。
"""
import io
import shutil
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ---------- 1) 卡片：卡头加统一开关，卡体加群区域 ----------
P1 = r'F:\QQAI\QQ-agent\ui\app\06-settings-render.js'
s = open(P1, encoding='utf-8').read()

if 'stk-group-area' in s:
    print('06-settings-render.js: 已打过补丁')
else:
    old = """    ${fold({
      id: 'card-sticker',
      icon: '😄',
      title: '表情包',
      sub: '收藏表情同步 / 发送积极度 / 提示词列举数',
      body: `"""
    new = """    ${fold({
      id: 'card-sticker',
      icon: '😄',
      title: '表情包',
      sub: '收藏表情同步 / 发送积极度 / 提示词列举数',
      // 卡头：统一开关（与「活跃设置」同款语义）
      extra: `<span class="ac-head-controls"><span class="ac-head-div"></span>
        <label class="switch" style="padding:0" title="开 = 所有群共用下面这套表情设置；关 = 每个群单独设置"><input type="checkbox" id="stk-unified" ${c.sticker?.unifiedSticker !== false ? 'checked' : ''} /><span class="track"><span class="thumb"></span></span><span style="font-size:12px">统一设置</span></label>
      </span>`,
      body: `"""
    assert old in s, '未找到表情包卡片'
    s = s.replace(old, new, 1)

    old_tail = """        <div class="hint">
          每次唤醒时，系统会把收藏表里最多这么多个表情包列进提示词供模型挑选。
          列得越多模型选择越丰富，但 token 成本也越高；收藏很多时适当调大，收藏少或想省 token 就调小。
        </div>
      </div>`
    })}"""
    new_tail = """        <div class="hint">
          每次唤醒时，系统会把收藏表里最多这么多个表情包列进提示词供模型挑选。
          列得越多模型选择越丰富，但 token 成本也越高；收藏很多时适当调大，收藏少或想省 token 就调小。
        </div>
      </div>
      <div id="stk-group-area" style="margin-top:14px;border-top:1px dashed rgba(128,128,128,.3);padding-top:12px">
        <div class="field">
          <label>要单独设置的群聊（来自白名单，点击切换）</label>
          <div class="ac-group-buttons" id="stk-group-buttons"></div>
        </div>
        <div id="stk-group-editor"></div>
        <div style="margin-top:8px">
          <button class="btn btn-small btn-danger" id="stk-group-clear" type="button">清除该群的单独设置</button>
        </div>
        <div class="hint">单群设置立即生效并自动保存；未单独设置的群沿用上面的全局值。</div>
      </div>`
    })}"""
    assert old_tail in s, '未找到表情包卡片尾部'
    s = s.replace(old_tail, new_tail, 1)
    shutil.copy2(P1, P1 + '.bak_stkper')
    open(P1, 'w', encoding='utf-8').write(s)
    print('06-settings-render.js: 已加统一开关 + 群区域')

# ---------- 2) 保存：收集 unifiedSticker（groupOverrides 走 state.config，不在 DOM） ----------
P2 = r'F:\QQAI\QQ-agent\ui\app\08-modals.js'
t = open(P2, encoding='utf-8').read()
if 'unifiedSticker' in t:
    print('08-modals.js: 已打过补丁')
else:
    old = """    patch.sticker = {
      ...(c.sticker || {}),
      enabled: chk('#cfg-sticker', !!c.sticker?.enabled),"""
    new = """    patch.sticker = {
      ...(c.sticker || {}),
      // 分群开关；groupOverrides 由群编辑器直接写进 c.sticker 后随 ...(c.sticker) 一起提交
      unifiedSticker: chk('#stk-unified', c.sticker?.unifiedSticker !== false),
      enabled: chk('#cfg-sticker', !!c.sticker?.enabled),"""
    assert old in t, '08-modals.js 未找到 patch.sticker'
    t = t.replace(old, new, 1)
    shutil.copy2(P2, P2 + '.bak_stkper')
    open(P2, 'w', encoding='utf-8').write(t)
    print('08-modals.js: patch.sticker 已带上 unifiedSticker')

# ---------- 3) 事件：挂载群编辑器 ----------
P3 = r'F:\QQAI\QQ-agent\ui\app\07-settings-events.js'
u = open(P3, encoding='utf-8').read()
if 'mountStickerGroupEditor' in u:
    print('07-settings-events.js: 已打过补丁')
else:
    anchor = """  const acRoot = $('#ac-editor');"""
    assert anchor in u, '07 未找到 ac-editor 挂载点'
    mount = """  // ── 表情包分群编辑器（与活跃设置同款交互：卡头统一开关 + 群按钮）──
  mountStickerGroupEditor();

"""
    # 函数定义放在 bindSettingsEvents 之外也可以：它用到的 scheduleSave 在这里，所以内联定义
    impl = """
  /**
   * 表情包分群编辑器。
   *
   * 数据形状：state.config.sticker.groupOverrides = { "群号": { enabled, encourage, promptMaxStickers } }。
   * 编辑即写 state.config，再走一次自动保存（与其它聊天设置字段同一条链路），
   * 所以没有「保存/取消」按钮，也不会和其他字段的草稿互相覆盖。
   */
  function mountStickerGroupEditor() {
    const area = $('#stk-group-area');
    const unifiedBox = $('#stk-unified');
    if (!area || !unifiedBox) return;
    const cfg = () => (state.config || {});
    const stickerOf = () => (cfg().sticker || (cfg().sticker = {}));
    const groups = () => (Array.isArray(cfg().allow?.groups) ? cfg().allow.groups.map(String) : []);
    const overrides = () => (stickerOf().groupOverrides || (stickerOf().groupOverrides = {}));
    let activeGid = '';

    const syncVisibility = () => {
      const unified = unifiedBox.checked !== false;
      area.style.display = unified ? 'none' : '';
      if (!unified) renderChips();
    };

    const renderChips = () => {
      const box = $('#stk-group-buttons');
      if (!box) return;
      const list = groups();
      if (!activeGid && list.length) activeGid = list[0];
      box.innerHTML = list.map((gid) => {
        const has = overrides()[gid] && typeof overrides()[gid] === 'object';
        const name = (typeof chatNameOf === 'function' ? chatNameOf(gid) : '') || gid;
        return `<button type="button" class="btn btn-small stk-group-btn${gid === activeGid ? ' btn-primary' : ''}" data-gid="${esc(gid)}">${esc(name)}${has ? ' ·' : ''}</button>`;
      }).join('') || '<span class="hint">白名单里还没有群</span>';
      renderEditor();
    };

    const renderEditor = () => {
      const box = $('#stk-group-editor');
      if (!box) return;
      if (!activeGid) { box.innerHTML = ''; return; }
      const cur = overrides()[activeGid] || {};
      const g = stickerOf();
      const name = (typeof chatNameOf === 'function' ? chatNameOf(activeGid) : '') || activeGid;
      const lvl = Number.isFinite(Number(cur.encourage)) ? Number(cur.encourage) : Number(g.encourage ?? 1);
      const max = Number.isFinite(Number(cur.promptMaxStickers)) ? Number(cur.promptMaxStickers) : Number(g.promptMaxStickers ?? 10);
      const en = cur.enabled === true || cur.enabled === false ? cur.enabled : (g.enabled !== false);
      box.innerHTML = `
        <div class="field-row">
          <div class="field"><label>${esc(name)} · 发表情积极程度</label>
            <select id="stk-g-encourage">
              ${(typeof STICKER_LEVELS !== 'undefined' ? STICKER_LEVELS : [[0, '0 · 不鼓励'], [1, '1 · 偶尔'], [2, '2 · 较积极'], [3, '3 · 很积极']])
                .map(([v, label]) => `<option value="${v}" ${Number(v) === lvl ? 'selected' : ''}>${esc(label)}</option>`).join('')}
            </select></div>
          <div class="field"><label>提示词列举数量（1~50）</label>
            <input type="number" id="stk-g-promptmax" min="1" max="50" value="${esc(max)}" /></div>
        </div>
        <div class="checkbox-row"><input type="checkbox" id="stk-g-enabled" ${en ? 'checked' : ''} />
          <label for="stk-g-enabled">该群启用表情包</label></div>`;

      const persist = () => {
        const all = overrides();
        all[activeGid] = {
          ...(all[activeGid] || {}),
          encourage: Math.min(3, Math.max(0, Number($('#stk-g-encourage')?.value) || 0)),
          promptMaxStickers: Math.min(50, Math.max(1, Number($('#stk-g-promptmax')?.value) || 10)),
          enabled: !!$('#stk-g-enabled')?.checked
        };
        scheduleSave(300);
      };
      for (const sel of ['#stk-g-encourage', '#stk-g-promptmax', '#stk-g-enabled']) {
        $(sel)?.addEventListener('change', persist);
      }
    };

    unifiedBox.addEventListener('change', () => {
      syncVisibility();
      scheduleSave(300);
    });

    $('#stk-group-buttons')?.addEventListener('click', (e) => {
      const btn = e.target.closest?.('.stk-group-btn');
      if (!btn) return;
      activeGid = String(btn.dataset.gid || '');
      renderChips();
    });

    $('#stk-group-clear')?.addEventListener('click', () => {
      if (!activeGid) return;
      delete overrides()[activeGid];
      renderChips();
      scheduleSave(300);
    });

    syncVisibility();
  }
"""
    u = u.replace(anchor, mount + anchor, 1)
    # 把实现插到 bindSettingsEvents 函数末尾之前：找函数结尾标记
    anchor_fn = "  function mountActiveConfigEditor"
    # 实现放文件末尾（函数声明会提升，闭包内可访问 scheduleSave）
    u = u.rstrip() + '\n' + impl
    shutil.copy2(P3, P3 + '.bak_stkper')
    open(P3, 'w', encoding='utf-8').write(u)
    print('07-settings-events.js: 已加群编辑器挂载与实现')
