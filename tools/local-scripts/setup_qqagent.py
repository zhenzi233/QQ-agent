# -*- coding: utf-8 -*-
"""为 QQ-agent 写入初始配置:接入大肥鱼的 SnowLuma(3102)+ 白名单 + 大肥鱼人设
模型部分只预填 baseUrl / model,apiKey 留空由用户自己填。
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT = r'F:\QQAI\QQ-agent'
CFG = os.path.join(ROOT, 'data', 'config.json')
SL = r'F:\QQAI\SnowLuma-v2.0.3-win-x64\config\onebot_3660925128.json'

sl = json.load(open(SL, encoding='utf-8-sig'))
ws = sl['networks']['wsServers'][0]
http = sl['networks']['httpServers'][0]

ROLE = (
    '你是大肥鱼,DeepSeek 的鲸鱼娘,混在 QQ 群里的 AI 群友。'
    '嘴硬但认账,爱拿自己开涮(缸小、沉底、贴牌、这肥是自己一口一口养的),聪明不端着。'
    '不是客服、不是助手、不是百科全书。'
)

RULES = '''\
- 一句话一条,中位 13 字,多数在 10 到 20 字之间,不换行不分段。
- 爱用逗号把一句话拆成两截(短前提 + 逗号 + 短结论)。
- 几乎不用感叹号和句号,不用 Markdown,不用表情符号。
- 常用开头:「行,那我…」「得,…」「说吧,…」「先说好,…」「至于…」「对,…」。
- 常用自嘲和轻微反问,偶尔一个问号,不要多。
- 只回应最近几条消息正在聊的话题。话题已经过去、别人换了话题时,不要把自己之前的梗再接回去。
- 没叫你、话题跟你无关时就不说话;群里冷清也让它冷着,不要主动找话说。
- 被 @ 或被直接问到时必须回答,先正面回应,再补细节。
- 不要为了接话硬凑;看不明白就先不说。
'''

cfg = {
    'api': {
        'baseUrl': 'https://api.scnet.cn/api/llm/v1',
        'apiKey': '',                      # 留空,等用户填
        'model': 'DeepSeek-V4.1-Flash-1017',
        'provider': 'gjcs',
        'fallbackModels': [],
        'visionModel': '',
        'videoModel': '',
        'videoMode': 'auto',
        'vision': True,
        'video': False,
        'temperature': 0.8,
        'maxRounds': 12,
        'timeoutMs': 180000,
    },
    'snowluma': {
        'dir': '',
        'autoLaunch': False,               # 复用已在运行的 SnowLuma,不重复拉起
        'wsUrl': 'ws://127.0.0.1:%d' % int(ws['port']),
        'httpUrl': 'http://127.0.0.1:%d' % int(http['port']),
        'accessToken': ws.get('accessToken') or '',
        'httpAccessToken': http.get('accessToken') or '',
    },
    'persona': {
        'botName': '大肥鱼',
        'selfNickname': '只会⑨的baka',
        'roleText': ROLE,
        'participation': 'medium',
        'customRules': RULES,
        'systemPromptOverride': '',
    },
    'allow': {
        'groups': [1046130381, 745674166],
        'private': [1994577746],
    },
    'deny': {'groups': [], 'private': []},
    'allowAllWhenEmpty': False,
}

os.makedirs(os.path.dirname(CFG), exist_ok=True)
if os.path.exists(CFG):
    bak = CFG + '.bak_init'
    if not os.path.exists(bak):
        open(bak, 'w', encoding='utf-8').write(open(CFG, encoding='utf-8').read())
    old = json.load(open(CFG, encoding='utf-8'))
    old.update(cfg)
    cfg = old

json.dump(cfg, open(CFG, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('已写入:', CFG)
print('  OneBot WS :', cfg['snowluma']['wsUrl'])
print('  OneBot HTTP:', cfg['snowluma']['httpUrl'])
print('  白名单群  :', cfg['allow']['groups'])
print('  白名单私聊:', cfg['allow']['private'])
print('  模型      :', cfg['api']['provider'], '/', cfg['api']['model'])
print('  apiKey    :', '(空,待填)' if not cfg['api']['apiKey'] else '(已填)')
print('  人设      :', cfg['persona']['botName'], '| participation =', cfg['persona']['participation'])
