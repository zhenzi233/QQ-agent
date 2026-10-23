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

## 脚本

`tools/local-scripts/` 下是本机维护脚本（转发展开修复、看图分页、表情指纹、表情库迁移、
向 QQ-agent 写配置等）。一次性或可重放的运维脚本，不参与运行时。

## 启动

`启动控制台.bat` → headless 模式，浏览器访问 `http://127.0.0.1:3210`。

## 注意

- `data/` 不进版本库（含聊天记录与 API Key）
- 上游已在 `0.5(unfinished)/` 重构架构，本分支不跟进；升级需重新移植上述改动
