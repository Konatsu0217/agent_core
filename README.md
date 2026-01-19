### 核心目录结构
```
agent_core/
├── main.py                      # Agent Core 主服务入口
├── run_all.py                   # 一键启动脚本（同时启动所有微服务和前端）
├── config/                      # 统一配置文件目录
│   ├── core.json                # 主服务配置
│   ├── mcp_servers.json         # MCP (Model Context Protocol) 枢纽配置
│   ├── pe.json                  # Prompt Engine 配置
│   ├── tts.json                 # TTS 引擎配置
│   └── ...
├── src/                         # 核心源代码
│   ├── agent/                   # 智能体逻辑实现 (如 FastAgent)
│   ├── infrastructure/          # 基础设施层 (LLM客户端, MCP/PE集成, 记忆管理)
│   ├── interfaces/              # 接口层 (Restful API, WebSocket)
│   ├── domain/                  # 领域模型与数据定义
│   └── shared/                  # 共享工具类 (配置解析, 日志管理)
├── tools/                       # 集成工具与子服务
│   ├── mcp_hub/                 # MCP 枢纽服务器，用于统一管理外部工具
│   ├── pe_server/               # Prompt Engine 服务，动态管理提示词模板
│   ├── tts/                     # TTS (Text-to-Speech) 语音合成引擎
│   ├── danmaku_proxy_service/   # 弹幕代理服务，支持 Bilibili 等直播平台
│   ├── motion_drive/            # 动作驱动逻辑与 VRMA 文件管理
│   └── bvh_converter/           # BVH 到 VRMA 的格式转换工具
├── webUI/                       # 基于 Vite + React 的 3D 交互前端
└── test/                        # 单元测试与 Demo 演示脚本
```

## 快速开始

### 1. 环境准备

确保已安装 Python 3.10+ 和 Node.js。

安装 Python 依赖：
```bash
pip install -r requirements.txt
```

安装前端依赖：
```bash
cd webUI
npm install
```

### 2. 配置说明

1.  在项目根目录下创建 `api.key` 文件，配置你的 LLM 供应商 API Key：
    ```json
    {
        "openapi_key": "your-api-key"
    }
    ```
2.  检查 `config/` 目录下的各项 JSON 配置文件，根据需要修改端口或服务地址。

### 3. 启动项目

使用一键启动脚本，它将自动启动 MCP Hub、PE Server、主服务以及前端界面：
```bash
python run_all.py
```

启动后：
-   **主服务**: [http://localhost:8000](http://localhost:8000)
-   **前端界面**: [http://localhost:5174](http://localhost:5174) (默认)
-   **MCP Hub**: [http://localhost:9000](http://localhost:9000)
-   **PE Server**: [http://localhost:8001](http://localhost:8001)


## RoadMap

- [x] 重构项目目录结构，提升模块化程度。
- [x] 整合 MCP Hub 工具管理。
- [ ] 接入视觉能力。
- [ ] Agent 路由化。
