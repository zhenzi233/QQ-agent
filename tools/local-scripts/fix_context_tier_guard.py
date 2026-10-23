# -*- coding: utf-8 -*-
"""修复：实跑重掷没命中(未触发)时仍在零上下文下开口

症状：会话记录里 `tier=0 past=0 reason=未触发`，但 `sent=1/2`——
模型在**没有任何历史**的情况下被叫起来说话，表现就是「不联系上下文」。

原因：onIncoming 时掷骰命中 → 排了等待唤醒；唤醒时（按 prompt.js 注释的
设计）会对同一批消息**重掷一次**，没命中就返回 shouldRespond=false。
wake 里只把它记进 tierResult，**没有据此拦下运行**，于是带着 count=0 的历史
继续调模型，模型照样开口。

修法：wake 里在算出 effectiveTier 后，若「非主动机会 + 非活跃期 + !shouldRespond」，
按设计标已读、收掉等待会话、直接返回，不建会话不调模型。
"""
import io
import shutil
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

P = r'F:\QQAI\QQ-agent\src\orchestrator.js'
s = open(P, encoding='utf-8').read()

if '重掷未命中' in s:
    print('已打过补丁，跳过')
    raise SystemExit

ANCHOR = """    const activeState = this.#activeState(chatKey);
    const effectiveTier = activeState
      ? { tier: 3, count: Math.max(0, Number(storeConfigForChat(chatKey).historyCount) || 80), reason: `活跃期（话题：${activeState.topic}）`, shouldRespond: true }
      : tierResult;
"""

GUARD = ANCHOR + """
    // 重掷未命中：onIncoming 时命中过，唤醒时重掷没命中（随机档的二次抽签）。
    // prompt.js 的约定是「调用方标已读、不建会话、不调模型」；这里必须真的拦下，
    // 否则会带着 count=0 的历史照样开口——表现就是"这bot不联系上下文"。
    if (!proactive && !activeState && !effectiveTier.shouldRespond) {
      this.store.markAllRead(chatKey);
      this.emit('chat-update', chatKey);
      if (waitingSessionId) this.#discardWaiting(waitingSessionId);
      return;
    }
"""

assert ANCHOR in s, '未找到档位计算块'
shutil.copy2(P, P + '.bak_tierguard')
s = s.replace(ANCHOR, GUARD, 1)
open(P, 'w', encoding='utf-8').write(s)
print('已加入「重掷未命中就不跑」的拦截')
