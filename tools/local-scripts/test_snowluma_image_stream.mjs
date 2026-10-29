// 测试 SnowLuma 流式图片下载：download_file_image_stream
// 用法：node test_snowluma_image_stream.mjs <file_id | 文件名 | URL>
// 帧格式是包着的：{status, data:{type:"stream", data_type:"file_info"|"file_chunk"|"file_complete", ...}}
import WebSocket from 'ws';

const TOKEN = '5pxzyUSJDzEHM6AT87wtN9963plcGZIrO1QOpWiFjrM';
const target = process.argv[2] || '';
if (!target) { console.log('缺少参数'); process.exit(2); }

const ws = new WebSocket('ws://127.0.0.1:3102', { headers: { Authorization: `Bearer ${TOKEN}` } });
let bytes = 0;
let chunks = 0;
let done = false;

const finish = (code, text) => {
  if (done) return;
  done = true;
  console.log(text);
  try { ws.close(); } catch {}
  process.exit(code);
};

const timer = setTimeout(() => finish(1, `超时（收到 ${chunks} 块 / ${bytes} 字节）`), 40000);

ws.on('open', () => {
  ws.send(JSON.stringify({ action: 'download_file_image_stream', params: { file: target, chunk_size: 65536 }, echo: 't1' }));
});

ws.on('message', (raw) => {
  let msg;
  try { msg = JSON.parse(raw.toString()); } catch { return; }
  if (!msg.echo) return;                       // 跳过 meta_event / heartbeat
  if (msg.retcode !== undefined && msg.retcode !== 0 && msg.status !== 'ok') {
    clearTimeout(timer);
    finish(1, `失败 retcode=${msg.retcode} ${msg.message || msg.wording || ''}`);
    return;
  }
  const d = msg.data || {};
  const kind = d.data_type || d.type;
  if (kind === 'file_info') {
    console.log(`file_info: name=${d.file_name} size=${d.file_size} chunk=${d.chunk_size}`);
  } else if (kind === 'file_chunk' || kind === 'data_chunk') {
    chunks += 1;
    bytes += Buffer.from(String(d.data || ''), 'base64').length;
  } else if (kind === 'file_complete' || kind === 'data_complete') {
    clearTimeout(timer);
    finish(0, `完成: 声明 ${d.total_bytes} 字节 / 实收 ${bytes} 字节 / ${chunks} 块`);
  }
});

ws.on('error', (e) => finish(1, `WS 错误: ${e.message}`));
