# 快速开始

## 大纲请看 agent_core_guide.md 感谢claude（
```
agent_core/
├── main.py                      # 入口文件，启动 FastAPI 服务
├── global_config.py             # 配置加载模块
├── requirements.txt             # 依赖列表
├── README.md                    # 项目说明
├── global_statics.py            # 全局静态变量
│
├── core/                        # 核心模块
│   ├── __init__.py
│   ├── basic_work_flow.py .     # 最原始的agent流程
│   ├── (WIP)orchestrator.py     # 🔥 调度器（核心）
│   ├── (WIP)event_router.py     # 🔥 事件路由（Planning）
│   │   ==== 这里的设计想法：一个core可以有多个agent，分别处理不同程度的query和任务，eg.视觉agent、文本agent ====
│   ├── agent_interface.py       # 智能体接口
│   ├── (WIP)fast_agent.py       # 快请求智能体实现
│   └── (WIP)request_tracker.py  # 请求追踪器
│
├── clients/                     # 外部服务客户端
│   ├── __init__.py
│   ├── llm_client.py            # LLM 客户端，包装了OpenAI的客户端，流式
│   ├── pe_client.py             # PE Server 客户端
│   ├── mcp_client.py            # MCP Hub 客户端
│   └── session_client.py        # Session Manager 客户端
│
├── models/                      # 数据模型
│   ├── __init__.py
│   └── (WIP)agent_data_model.py # 协议消息模型
│
├── tools/                       # 玩法工具
│   ├── __init__.py
│   ├── tts/                     # 多种edgeTTS的调用包装
│   └── TBD                      # vrm还没补，依赖前端多
│
├── handlers/                    # 特殊处理器
│   ├── __init__.py              # 输出层到TTS/前端/Vrm/其他玩法
│   ├── TBD                      # 工具调用集成在mcphub里了
│   └── TBD                      # 流式响应处理器
│
├── utils/                       # 工具函数
│   ├── __init__.py
│   ├── config_manager.py        # 配置管理模块
│   ├── (WIP)logger.py           # 日志配置模块 ⬅️现在会到处拉log文件夹
│   └── connect_manager.py       # 连接管理模块,其实暂时不需要
│
└── tests/                       # 测试文件
    ├── test_orchestrator.py
    ├── test_llm_client.py
    └── test_tool_calls.py
```

## 依赖

### 外部openapi接口的LLM供应商
推荐硅基流动，比较便宜，而且有赠送金，[硅基流动](https://cloud.siliconflow.cn/me/models)

（我的[邀请链接](https://cloud.siliconflow.cn/i/zYdjNNQB)双赢白送2000万token❤️）

model_name = 模型全名，去对应位置复制

openapi_url = https://api.siliconflow.cn/v1 硅基流动的api

openapi_key = 生成一个，别泄漏，扣钱的

请创建一个 api.key 文件，里面写入openapi_key

```json
{
    "openapi_key": "your-api-key"
}
```

### [PE server](https://github.com/Konatsu0217/agent_pe_server) /dev

- 关注一下url和端口，运行main.py就行

### [MCP Hub](https://github.com/Konatsu0217/agent_mcp_hub) /dev

- 需要先启动MCP服务，运行 ./mcp_server/mcp_server_example.py
- 再启动mcp_hub服务端，运行 mcp_center_server.py