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
