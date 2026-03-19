# Amadues Live2D Client

Live2D 虚拟主播客户端，通过 WebSocket 连接 Amadues Gateway 后端。

## 架构

```
┌─────────────────────────────────────────────┐
│              Amadues Gateway                │
│  ┌──────────┐  ┌─────────┐  ┌───────────┐  │
│  │ WS Server│  │  Agent  │  │ HTTP/Files│  │
│  │  :8788   │  │ (LLM)  │  │   :8787   │  │
│  └────┬─────┘  └────┬────┘  └─────┬─────┘  │
│       │             │             │         │
└───────┼─────────────┼─────────────┼─────────┘
        │ WebSocket   │             │ HTTP (audio files)
        │             │             │
┌───────┼─────────────┼─────────────┼─────────┐
│       ▼             │             ▼         │
│  ┌──────────┐       │       ┌───────────┐   │
│  │WS Client │       │       │AudioPlayer│   │
│  └────┬─────┘       │       └─────┬─────┘   │
│       │                           │         │
│       ├──── text_delta ──→ Subtitle         │
│       ├── audio_delta ──→ Audio + LipSync   │
│       ├─ expression ──→ Live2D Expression   │
│       │                                     │
│  ┌──────────────────────────────┐           │
│  │     Live2D Controller        │           │
│  │ (pixi.js + pixi-live2d-display)         │
│  └──────────────────────────────┘           │
│              Client (Browser)               │
└─────────────────────────────────────────────┘
```

## 快速开始

### 1. 安装依赖

```bash
cd client
npm install
```

### 2. 放置 Live2D 模型

将 Live2D 模型文件放到 `public/models/` 目录下。例如：

```
public/models/
└── haru/
    ├── haru_greeter_t03.model3.json
    ├── haru_greeter_t03.moc3
    ├── haru_greeter_t03.physics3.json
    └── textures/
        └── ...
```

免费模型推荐：
- [Live2D 官方示例模型](https://www.live2d.com/en/learn/sample/)
- [Cubism SDK 附带的 Haru/Hiyori 模型](https://github.com/Live2D/CubismWebSamples)

### 3. 启动后端

```bash
# 在项目根目录
amadeus gateway --ws-port 8788 --http-port 8787
```

### 4. 启动客户端

```bash
cd client
npm run dev
```

访问 `http://localhost:3000`

### 5. URL 参数配置

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `ws` | WebSocket 地址 | `ws://127.0.0.1:8788` |
| `http` | HTTP 地址 | `http://127.0.0.1:8787` |
| `model_path` | Live2D 模型路径 | `./models/haru/haru_greeter_t03.model3.json` |
| `agent_id` | Agent ID | `live2d` |

示例：
```
http://localhost:3000?ws=ws://192.168.1.100:8788&model_path=./models/my_model/model.json
```

## 通信协议

### 客户端 → 服务端

```json
{
  "event_id": "unique_id",
  "session_id": "session_hex",
  "type": "user_message",
  "ts": 1234567890.123,
  "source": "client",
  "payload": { "session_id": "xxx", "text": "你好" },
  "version": "1.0"
}
```

### 服务端 → 客户端

| 事件 | 说明 | 客户端处理 |
|------|------|------------|
| `state` | 会话就绪 | 启用输入框 |
| `text_delta` | 文字增量 | 追加字幕 |
| `audio_delta` | TTS 音频 | 播放 + 口型同步 |
| `expression_delta` | 表情/动作 | 驱动 Live2D |
| `final` | 完成 | 显示最终字幕 |
| `error` | 错误 | 显示错误日志 |

## 项目结构

```
client/
├── index.html              # 入口 HTML
├── package.json
├── tsconfig.json
├── vite.config.ts
├── public/
│   └── models/             # Live2D 模型文件
└── src/
    ├── app.ts              # 主应用（整合所有模块）
    ├── ws-client.ts        # WebSocket 通信层
    ├── audio-player.ts     # TTS 音频播放 + 口型同步
    ├── live2d-controller.ts # Live2D 模型控制
    ├── subtitle.ts         # 字幕管理
    └── style.css           # 样式
```

## 扩展建议

### 让后端支持 expression_delta

在后端的 `GATEWAY_SYSTEM_PROMPT` 或 Agent Profile 中加入：

```
当你想表达情感时，调用 emit_event(type='expression_delta', payload={'expression': 'happy'})。
支持的 expression: neutral, happy, sad, angry, surprise, thinking。
支持的 motion: idle, greeting, nod（需与模型匹配）。
```

### OBS 集成

客户端页面可以直接作为 OBS 浏览器源：
1. OBS → 来源 → 浏览器
2. URL: `http://localhost:3000`
3. 勾选「关闭时不渲染」
4. 设置为背景透明即可叠加到直播画面

