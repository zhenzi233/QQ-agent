# QQ-agent（本地定制分支）

本仓库 fork 自 [K0nd1us/QQ-agent](https://github.com/K0nd1us/QQ-agent)，只记录本机运行所需的改动。

- 基线：`95f8f62`（0.4 版本）
- 分支：`local/custom-0.4`
- `main` 保持上游原样，开发都在本分支

## 本机改了什么

### 1. 会话页按群筛选

`ui/index.html`、`ui/app/02-sse-sessions.js`、`ui/app/10-feedback.js`

会话列表原本按时间倒序混排，两个群的运行记录交叠，难以分辨。加了一个下拉框：
默认「全部会话」，选项从当前会话动态生成，选中后只显示该群记录，计数同步跟随。

### 2. 合并转发用 res_id 展开

`src/onebot.js`、`src/app.js`、`src/tools.js`

原实现用 `get_forward_msg({ message_id })`。SnowLuma 只认转发卡片的 `res_id`，
传 `message_id` 时它会退回把 message_id 当 id 用，QQ 侧返回
`download forward message payload is empty`，导致转发内容永远展开失败。

改为先用 `get_msg` 取出 forward 段的 `data.id`，再用 `{ id }` 调用，失败才退回旧路径。
收消息时与 `read_forward` 工具两处都改了。

### 3. 看图分页

`src/tools.js`（`get_message_images`）

原实现一次把消息里所有图片塞进 `image_url` 部件。合并转发里 30 张图约 13 MB，
base64 后约 18 MB，模型接口直接 400/413，表现就是「看不到聊天记录里的图片」。

新增 `offset` / `limit` 参数（默认 4 张，最多 6 张），返回文案会告知还剩多少、怎么继续翻。

### 4. 表情包指纹与本群计数

`src/onebot.js`、`src/app.js`

群友发的表情和普通图片原本都渲染成 `[图片]`，模型无法判断「同一个表情又发了一次」，
每次反应都像第一次见。

- 表情渲染成 `[表情包#2A29FE2F]`（取协议端文件名前 8 位，即 QQ 侧 md5）
- 入库时按会话累加次数，第二次起变成 `[表情包#2A29FE2F 本群第3次]`
- 计数存 `data/sticker-seen.json`，按会话隔离，**按天统计**：本地时间每天 0 点清零，今天的次数不带进明天

### 5. 唤醒重掷未命中时不再零上下文开口

`src/orchestrator.js`

响应档位在「收到消息」和「唤醒」两处各掷一次骰（随机档的二次抽签，代码注释说明是有意设计）。
唤醒那次没命中时返回 `shouldRespond=false`（档位 0、历史 0 条），但原实现只把这个结果
记进会话日志，**没有据此拦下运行**——于是带着 0 条历史继续调模型，模型照样发言。

会话记录里能直接看到：`tier=0 past=0 reason=未触发` 却 `sent=1~2`。
表现就是「这机器人不联系上下文」，其实是它根本没拿到上下文。

现在按 `prompt.js` 的既有约定真的拦下：标已读 → 收掉等待会话 → 不建会话不调模型。
判定走「非主动机会 + 非活跃期 + 未命中」三个条件，被 @、关键词命中、活跃期都不受影响。

### 6. 补图消息标注调用参数

`src/orchestrator.js`

工具返回的图片不能塞进 tool 消息（多数 OpenAI 兼容端点不接受），代码会另发一条 user 消息补图，
文案原本是「以下是工具 get_message_images 返回的 1 张图片」——**没有调用参数**。

连续两次看图（先看 #A 再看 #B）时，两条补图消息文本完全相同，模型只能靠顺序猜，
于是出现「说的是第一条图的 mid、描述的却是最后一张图」。

现在补图消息带上本次调用的参数（`messageId=...`），并写明「这些图只属于上面这一次调用」。

### 7. 动图改发「按时长分档的帧拼图」

`src/gif-to-video.js`、`src/tools.js`

只开图片输入（`api.video = false`）时，GIF 原本按原图发给模型。网关不报错，
但大多数模型只解码**第一帧**——模型会说「只拿到第一帧，看不到后面」。

现在 GIF 进来先用 ffprobe 量时长，**按时长决定格数**，再用 ffmpeg 拼成一张 PNG：

| GIF 时长 | 帧数 | 排布 | 每格长边 |
|---|---|---|---|
| ≤1.5s | 4 | 2×2 | 360px |
| ≤3s | 6 | 3×2 | 320px |
| ≤6s | 8 | 4×2 | 240px |
| ≤12s | 12 | 4×3 | 240px |
| >12s | 16 | 4×4 | 240px |

单帧 GIF（帧数不足格数）拼不出图时，自动退回只取首帧。整张拼图控制在 ≈960px 见方，
text 里说明这是动图的帧拼图，动作走向就能看到了。拼图失败则退回原样发送，
原有的「被拒收 → 换首帧重试」降级路径不受影响。

### 8. 上下文里只保留最近 2 张图片

`src/llm.js`

工具返回的图片会以「text + image_url」的 user 消息留在对话里，**之后每一轮请求都会重发**。
连续看图 8 次 = 8 张 base64 图在后 8 轮里反复上传：一次会话跑到 11 轮、14.6 万 token，
最后卡在思考之后不动。

现在每次请求前裁剪：只保留最近 2 条带图消息，更早的把图片部件换成一行文字提示
（文本与 tool 消息完全不动）。阈值可用 `api.keepRecentImages` 覆盖，0 = 不裁剪。

### 9. 应回而未回时补发草稿

`src/orchestrator.js`

模型有时把要说的话写在正文里、没调用 `send_message`。正文按设计不发 QQ，
项目自带的 reply-rescue 兜底又依赖 reply-safety 技能提供的 `reply.inline-calls`——
没装那个技能时兜底直接返回空，草稿被丢掉，界面上只剩一张「思考」卡片
（会话状态 `noreply`、`sent=0`）。

现在收尾处加了一层保守补发：**只对本来该回的场景**（私聊 / 被 @ / 1~2 档），
且正文看起来是成品短句时，用正常发送链路补发。

判定刻意保守：含「【】」思考标记、代码块、列表、或以「让我/我应该/先看看」开头的，
一律不发；超过 120 字不发。**宁可沉默，也不把内心戏发进群。**

### 10. 表情包支持分群设置

`src/config.js` / `src/prompt.js` / `src/orchestrator.js` + 设置页

`sticker.unifiedSticker`（默认 true=全群统一）+ `sticker.groupOverrides[群号]`，
解析函数 `stickerConfigForChat(chatKey)`：统一模式返回全局值，分群模式按群合并
（缺字段回落全局），只允许覆盖 `enabled / encourage / promptMaxStickers`。
设置页「表情包」卡片头部多了「统一设置」开关，关掉后出现群按钮和保存按钮。

### 11. 候选数超过 15 时不输出表情 id（已修）

`src/stickers.js`

`buildStickerContext(entries, max, { withId })` 原来默认 `withId = max <= 15`，
`max` 又被 `Math.min(30, …)` 截断。于是候选一调大，提示词里就**不带 id**，
而 `send_sticker` 的必填参数是 `stickerId` —— 模型拿不到 id，只能放弃或额外查一次，
表现为「**候选数越大、表情发得越少**」。

现在：`withId` 默认恒 true（可显式关掉），上限 30 → 60。单测已同步
（`test/sticker-context.mjs`）。

### 12. 引用的图片能看

`src/app.js` / `src/onebot.js` / `src/tools.js` / `src/safe-fetch.js`

三处问题叠在一起：

1. `resolveReply` 把非文本段映射成 CQ 类型名（`[image]`），且不带消息 id → 模型既不知道
   那是图、也没参数可调；现在映射成 `[图片]`/`[表情]`/`[语音]`…，并带出 `#id`，
   由 `onebot.js` 拼进引用块。
2. `get_message_images` 只查本会话存档 → 自己发的 / 太老的消息查不到；现在查不到就用
   `onebot.getMsg` 取原始段落兜底。
3. 本机 `file:///` 图片被当网络 URL 下载 → 必然失败；现在先读盘（支持「url 是目录 +
   file 是文件名」这种脏数据），读不到才走网络。取不回时给的是
   「原图已不可读，不要编造画面」，而不是一句「获取失败」。

附带修一个环境坑：**Clash/FlClash 的 fake-ip（198.18.0.0/15）** 会被
`safe-fetch` 判成内网而拦掉，导致开代理时所有图片抓取失败。现在只对这一段放行
（`security.allowFakeIpHosts`，默认开），真内网段照旧拦。

### 13. 搜索改走 DeepSeek API

`config.webSearch`

原默认是**抓 Bing 搜索结果页**，依赖能访问 `cn.bing.com`。实测：直连被墙、走代理
TLS 握手直接卡死（节点不可用），于是「一开代理搜索就挂」。

现在 `provider = deepseek`，走 `https://api.deepseek.com/responses` + `web_search` 工具，
由服务端搜，不依赖本机能不能上外网。代价是慢（约 10~12 秒）且只返回一段总结而非
多条带链接的结果。

## 脚本

`tools/local-scripts/` 下是本机维护脚本（转发展开修复、看图分页、表情指纹、表情库迁移、
上下文档位拦截、向 QQ-agent 写配置等）。一次性或可重放的运维脚本，不参与运行时。

## 启动

`启动控制台.bat` → headless 模式，浏览器访问 `http://127.0.0.1:3210`。

## 注意

- `data/` 不进版本库（含聊天记录与 API Key）
- 上游已在 `0.5(unfinished)/` 重构架构，本分支不跟进；升级需重新移植上述改动
