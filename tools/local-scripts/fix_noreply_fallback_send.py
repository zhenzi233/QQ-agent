# -*- coding: utf-8 -*-
"""修「思考完就没动静」：应回而未回时，把模型写好的那句补发出去

症状：私聊/被 @ 的会话跑完 status=noreply、sent=0，界面上只剩一张「思考」卡片。
原因：模型有时把要说的话写在正文里、没调用 send_message；正文按设计不发 QQ。
      项目里有 reply-rescue 兜底，但它依赖 reply-safety 技能提供的
      `reply.inline-calls` 能力——没装那个技能时兜底直接返回空，草稿就被丢掉了。

改法：在收尾处加一层保守兜底——只对「本来就该回」的场景（私聊 / 被 @ / 1~2 档），
且正文看起来是成品短句（不含思考标记、不是代码、长度 ≤120 字）时，用正常发送链路补发。
判定偏保守：拿不准就不发，宁可没回也不把内心戏发进群。
"""
import io
import shutil
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

P = r'F:\QQAI\QQ-agent\src\orchestrator.js'
s = open(P, encoding='utf-8').read()

if 'fallback-send-draft' in s:
    print('已打过补丁，跳过')
    raise SystemExit

HELPER = '''
  /**
   * 应回而未回时的保守补发（fallback-send-draft，2026-10-23）。
   *
   * 只处理这种情况：这一轮没发出任何消息，但触发场景本来就该回（私聊 / 被 @ / 1~2 档），
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

      // 取最后一条有正文的 assistant 消息
      let draft = '';
      for (let i = (session.messages || []).length - 1; i >= 0; i--) {
        const m = session.messages[i];
        if (m?.role !== 'assistant' || typeof m.content !== 'string') continue;
        draft = m.content.trim();
        if (draft) break;
      }
      if (!draft) return false;

      // 思考块不能发：出现【深度思考】就整条放弃（含它的正文通常是计划，不是话）
      if (draft.includes('【') || draft.includes('】')) return false;
      // 代码块 / 列表 / 明显的工作描述都不发
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

anchor = '    // 收尾：发过话 = done；没发 = noreply（这是正常选项）'
assert anchor in s, '未找到收尾处'
s = s.replace(anchor, HELPER.rstrip('\n') + '\n\n' + anchor, 1)

# 在状态判定前调用兜底
old_status = "    // 收尾：发过话 = done；没发 = noreply（这是正常选项）\n    const status = session.error ? 'error' : (session.sent.length > 0 ? 'done' : 'noreply');"
new_status = ("    // 收尾：应回而未回时先尝试补发（见 #fallbackSendDraft）\n"
              "    await this.#fallbackSendDraft(session, chatKey);\n"
              "    // 发过话 = done；没发 = noreply（这是正常选项）\n"
              "    const status = session.error ? 'error' : (session.sent.length > 0 ? 'done' : 'noreply');")
assert old_status in s, '未找到状态判定'
s = s.replace(old_status, new_status, 1)
shutil.copy2(P, P + '.bak_fallbacksend')
open(P, 'w', encoding='utf-8').write(s)
print('已加入应回未回的补发兜底')
