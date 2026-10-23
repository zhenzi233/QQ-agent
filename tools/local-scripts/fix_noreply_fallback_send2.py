# -*- coding: utf-8 -*-
"""修「思考完就没动静」：应回而未回时，把模型写好的那句补发出去（第 2 版）

上一版把方法插到了错误位置导致类结构被破坏，这次改为插在类内既有私有方法之前。
"""
import io
import shutil
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

P = r'F:\QQAI\QQ-agent\src\orchestrator.js'
s = open(P, encoding='utf-8').read()

if 'fallbackSendDraft' in s:
    print('已打过补丁，跳过')
    raise SystemExit

METHOD = '''  /**
   * 应回而未回时的保守补发（fallback-send-draft，2026-10-23）。
   *
   * 只处理：这一轮一条都没发出去，但触发场景本来就该回（私聊 / 被 @ / 1~2 档），
   * 且模型最后一条正文看起来是成品短句。判定刻意保守 —— 宁可沉默，也不把内心戏发进群。
   */
  async #fallbackSendDraft(session, chatKey) {
    try {
      if (!session || session.error) return false;
      if ((session.sent || []).length > 0) return false;
      const tier = Number(session.contextTier);
      const obligated = String(chatKey).startsWith('private:')
        || (Number.isFinite(tier) && tier >= 1 && tier <= 2);
      if (!obligated) return false;

      let draft = '';
      for (let i = (session.messages || []).length - 1; i >= 0; i--) {
        const m = session.messages[i];
        if (m?.role !== 'assistant' || typeof m.content !== 'string') continue;
        const text = m.content.trim();
        if (text) { draft = text; break; }
      }
      if (!draft) return false;

      // 思考块不能发：出现中文方括号标记通常就是计划/内心戏，整条放弃
      if (draft.includes('【') || draft.includes('】')) return false;
      if (draft.includes('```') || draft.startsWith('#') || draft.startsWith('- ')) return false;
      if (/^(让我|我应该|我需要|先看|先查|看看|检查一下)/.test(draft)) return false;
      if (draft.length > 120) return false;

      const res = await this.sender.sendTextBatch(chatKey, [draft], {});
      const sent = res?.sent || [];
      if (!sent.length) return false;
      session.sent.push(...sent.map((x) => ({ type: 'text', text: x.text, at: x.at })));
      session.fallbackSent = true;
      this.sessions.update(session.id);
      this.emit('session-update', session.id);
      console.log(`[orchestrator] ${chatKey} 补发未送出的草稿（${draft.length} 字）`);
      return true;
    } catch (error) {
      console.warn(`[orchestrator] 补发草稿失败: ${error?.message ?? error}`);
      return false;
    }
  }

'''

anchor_method = '  #buildConsolidateNote({ total, changed, failed, skipped, only, discoveredCount = 0 }) {'
assert anchor_method in s, '未找到类内插入点'
s = s.replace(anchor_method, METHOD + anchor_method, 1)

old_status = "    // 收尾：发过话 = done；没发 = noreply（这是正常选项）\n    const status = session.error ? 'error' : (session.sent.length > 0 ? 'done' : 'noreply');"
new_status = ("    // 收尾：应回而未回时先尝试补发（见 #fallbackSendDraft）\n"
              "    await this.#fallbackSendDraft(session, chatKey);\n"
              "    // 发过话 = done；没发 = noreply（这是正常选项）\n"
              "    const status = session.error ? 'error' : (session.sent.length > 0 ? 'done' : 'noreply');")
assert old_status in s, '未找到状态判定'
s = s.replace(old_status, new_status, 1)

shutil.copy2(P, P + '.bak_fallbacksend')
open(P, 'w', encoding='utf-8').write(s)
print('已插入补发兜底（类内）并接到收尾处')
