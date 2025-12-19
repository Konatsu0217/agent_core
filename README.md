# 快速开始
### 安装程序依赖
```bash
pip install -r requirements.txt
```
### 安装前端界面依赖
```bash
cd webUI
npm install
```

环境都配置好之后，回到根目录执行 run_all.py 即可启动所有服务(包括前端)


## 大纲请看 agent_core_guide.md 感谢claude（
```
agent_core/
├── main.py                      # 入口文件，启动 FastAPI 服务
├── core_config.json             # 核心配置
├── requirements.txt             # 依赖列表
├── README.md                    # 项目说明
├── global_statics.py            # 全局静态变量
├── clean_logs.sh
├── get_bvh_request.sh
├── run_all.py
├── api.key                      # OpenAPI 密钥
│
├── core/                        # 核心模块
│   ├── __init__.py
│   ├── agent_interface.py       # 智能体接口
│   ├── basic_work_flow.py       # 最原始的agent流程
│   └── fast_agent.py            # 快请求智能体实现
│
├── clients/                     # 外部服务客户端
│   ├── __init__.py
│   ├── llm_client.py            # LLM 客户端，包装OpenAI流式接口
│   ├── mcp_client.py            # MCP Hub 客户端
│   └── pe_client.py             # PE Server 客户端
│
├── models/                      # 数据模型
│   ├── __init__.py
│   └── agent_data_models.py     # 协议消息模型
│
├── handlers/                    # 特殊处理器
│   ├── __init__.py
│   ├── tts_handler.py
│   └── vrma_handler.py
│
├── utils/                       # 工具函数
│   ├── __init__.py
│   ├── config_schemas.py        # 统一配置
│   ├── config_manager.py        # 配置管理模块(准备废弃)
│   ├── connet_manager.py        # 连接管理模块
│   └── logger.py                # 日志配置模块
│
├── tools/                       # 工具与子模块
│   ├── __init__.py
│   ├── bvh_converter/           # BVH 转 VRMA 前端工具
│   ├── mcp_hub/                 # MCP Hub 相关
│   ├── motion_drive/            # 动作生成流程
│   ├── pe_server/               # PE Server 组件
│   └── tts/                     # TTS 引擎与服务
│
├── doc/                         # 文档
│   ├── agent_core_guide.md
│   ├── agent_paradigms_guide.md
│   ├── model_speed_test.md
│   └── moe_agent_architecture.md
│
├── config/                         # 统一配置
│   ├── core.json
│   ├── mcp_server.json
│   ├── motion.json
│   ├── pe.json
│   └── tts.json
│
├── test/                        # 测试文件
│   ├── test_basic_agent.py
│   ├── test_llm_client.py
│   └── test_tts/
│       ├── demo_relay_simple.py
│       ├── demo_sequential_play.py
│       └── demo_tts_streaming.py
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

# RoadMap

## 短期
- [ ] 解耦RAG，独立模块调用
- [ ] 改进agent整个的架构，参考 [深水区](https://www.zhihu.com/column/c_1955378545019823972)
- [ ] 创建agent_router, fine-tune Qwen-3-0.6B作为路由模型，根据输入选择合适的agent
- [ ] 尝试更多的骨骼动画模型，尝试部署和回收反馈，评估bad case

## 长期
- [ ] 实现ReAct Agent ---> core/react_agent.py
- [ ] 实现Plan-and-Solve Agent ---> core/plan_agent.py
- [ ] 外挂视觉能力 ---> tools/vision


