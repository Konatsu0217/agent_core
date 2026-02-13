# Agent Core 技术架构文档

## 项目概述

Agent Core 是一个多模态 AI Agent 运行时框架，提供完整的 Agent 生命周期管理、工具调用、记忆系统和多模态交互能力。该框架采用分层架构设计，支持多种 LLM 提供商和工具协议。

## 技术栈

- **后端框架**: FastAPI + uvicorn
- **通信协议**: HTTP REST + WebSocket
- **异步处理**: asyncio / asyncpg
- **数据库**: SQLite（用于 Agent 配置存储）
- **LLM 集成**: OpenAI 兼容 API
- **工具协议**: MCP (Model Context Protocol)
- **运行环境**: Python 3.10+

## 系统架构

### 分层架构图

```
┌─────────────────────────────────────────────────┐
│              Main/Entry Layer                    │
│         (back_end.py, runtime.py)                 │
├─────────────────────────────────────────────────┤
│            Coordinator Layer                      │
│       (agent_coordinator, work_flow_engine)       │
├─────────────────────────────────────────────────┤
│              Agent Layer                         │
│    (abs_agent.py, base_agents, agent_factory)    │
├─────────────────────────────────────────────────┤
│           Service Layer (DI)                     │
│         (container, services/interfaces)          │
├─────────────────────────────────────────────────┤
│           Context Layer                          │
│      (context_maker, manager, storage)            │
├─────────────────────────────────────────────────┤
│         Infrastructure Layer                     │
│    (clients, handlers, utils, logging, config)    │
├─────────────────────────────────────────────────┤
│              Domain Layer                         │
│         (data_models, events, enums)              │
└─────────────────────────────────────────────────┘
```

## 目录结构

```
src/
├── agent/                    # Agent 核心模块
│   ├── agent_profiles/       # Agent 配置文件目录
│   ├── storage/              # Agent 存储实现
│   ├── abs_agent.py          # Agent 抽象基类
│   ├── agent_factory.py      # Agent 工厂
│   └── base_agents.py        # 基础 Agent 实现
│
├── context/                  # 上下文管理层
│   ├── storage/              # 上下文存储实现
│   ├── augmenters.py         # 上下文增强器
│   ├── context.py            # 上下文数据模型
│   ├── context_maker.py     # 上下文构建器
│   └── manager.py            # 上下文管理器
│
├── coordinator/              # 协调与工作流
│   ├── agent_coordinator.py  # Agent 协调器
│   └── work_flow_engine.py   # 工作流引擎
│
├── di/                       # 依赖注入系统
│   ├── services/
│   │   ├── impl/            # 服务实现
│   │   └── interfaces/      # 服务接口
│   ├── container.py         # 服务容器
│   └── __init__.py
│
├── domain/                   # 领域模型
│   ├── agent_data_models.py  # Agent 数据模型
│   ├── danmaku_models.py     # 弹幕数据模型
│   └── events.py             # 事件定义
│
├── infrastructure/          # 基础设施层
│   ├── clients/              # 客户端集成
│   │   ├── bilibili_live_client/  # Bilibili 直播客户端
│   │   ├── llm_clients/            # LLM 客户端
│   │   ├── mcp_client.py           # MCP 客户端
│   │   ├── mem0ai_client.py        # mem0 记忆客户端
│   │   ├── pe_client.py            # PE 服务客户端
│   │   └── session_manager.py      # 会话管理客户端
│   ├── config/               # 配置管理
│   │   ├── config_manager.py      # 配置管理器
│   │   └── config_schemas.py       # 配置模式
│   ├── handlers/             # 处理器
│   │   ├── tts_handler.py          # TTS 处理器
│   │   └── vrma_handler.py         # VRMA 处理器
│   ├── logging/              # 日志系统
│   │   └── logger.py               # 日志器
│   └── utils/                # 工具类
│       ├── atomic_func.py         # 原子函数
│       ├── connet_manager.py      # 连接管理器
│       └── pipe.py                 # 进程管道
│
└── main/                     # 服务入口
    ├── back_end.py           # FastAPI 后端
    ├── runtime.py            # 运行时环境
    └── session_orchestrator.py  # 会话编排器
```

## 核心模块说明

### 1. 入口层 (main/)

#### back_end.py

FastAPI 应用主文件，负责：

- **应用初始化**
  - FastAPI 实例创建和配置
  - CORS 中间件配置
  - 生命周期管理 (lifespan)

- **WebSocket 端点**
  - 端点：`/ws/agent`
  - 处理客户端实时连接
  - 消息解析和路由

- **服务注册**
  ```python
  container.register("query_wrapper", DefaultQueryWrapper())
  container.register("tool_manager", McpToolManager())
  container.register("memory_service", Mem0MemoryService())
  container.register("prompt_service", PePromptService())
  container.register("session_service", DefaultSessionService())
  ```

- **API 端点**
  | 方法 | 路径 | 功能 |
  |------|------|------|
  | POST | `/api/agent/profile` | 上传 Agent 配置 |
  | GET | `/api/agent/profile/{agent_id}` | 获取 Agent 配置 |
  | GET | `/api/session/{session_id}/messages` | 获取会话消息 |
  | DELETE | `/api/session/delete` | 删除会话 |

#### runtime.py

会话运行时封装：

- **RuntimeSession**
  - 会话 ID 管理
  - Agent 实例关联
  - WebSocket 连接管理
  - TTS 处理器初始化
  - 事件总线 (EventBus)
  - 缓冲区管理

- **EventBus**
  - 事件订阅机制
  - 事件发布机制
  - 支持异步事件处理

### 2. 协调层 (coordinator/)

#### agent_coordinator.py

Agent 协调器，负责多 Agent 的管理和任务分发：

- **核心功能**
  - Agent 注册和注销
  - Agent 实例管理
  - 任务分发策略
  - Agent 选择和路由

- **任务分发**
  ```python
  async def process(request: AgentRequest, pipe: ProcessPipe, agent_id):
      if agent_id:
          agent = self.get_agent(agent_id)
          await run_with_pipe(agent, request, pipe)
      elif self.task_dispatcher:
          selected_agent = await self.task_dispatcher.select_agent(...)
          await run_with_pipe(selected_agent, request, pipe)
      else:
          default_agent = next(iter(self.agents.values()))
          await run_with_pipe(default_agent, request, pipe)
  ```

- **TaskDispatcher**
  - 基于请求内容的 Agent 选择
  - 关键词匹配策略
  - Agent 能力评估

### 3. Agent 层 (agent/)

#### abs_agent.py

Agent 核心实现，采用继承体系：

```
IBaseAgent (抽象接口)
│
├── BaseAgent
│   ├── ToolUsingAgent (支持工具调用)
│   │   └── 工具执行循环
│   │   ├── 工具调用解析
│   │   ├── 工具执行
│   │   ├── 审批流程处理
│   │   └── 结果处理
│   │
│   └── MemoryAwareAgent (支持记忆)
│       ├── 记忆添加
│       └── 记忆检索
│
└── ServiceAwareAgent (服务感知)
    └── 依赖注入处理
```

**执行模式**：

| 模式 | 说明 |
|------|------|
| `TEST` | 测试模式 |
| `ONE_SHOT` | 单轮对话模式 |
| `ReAct` | 推理-行动循环模式 |
| `Plan-and-Solve` | 计划与执行模式 |

**核心方法**：

```python
class BaseAgent:
    async def initialize()           # 初始化 Agent
    async def process(request, pipe)   # 处理用户请求
    def get_capabilities() -> dict     # 获取 Agent 能力
    def estimate_cost(request) -> dict  # 估算处理成本

class ToolUsingAgent:
    async def run_with_tools(pipe)     # 工具调用主循环
    async def append_tool_call(...)    # 添加工具调用记录

class MemoryAwareAgent:
    async def memory_hook(request, text)  # 记忆钩子
    async def add_memory(session_id)      # 添加记忆
```

**LLM 工具调用流程**：

```python
async def run_llm_with_tools(llm_client, context, pipe):
    # 1. 构建消息
    messages = [
        {"role": "system", "content": context.system_prompt},
        ...context.messages
    ]

    # 2. 流式调用 LLM
    async for raw in llm_client.chat_completion_stream(messages):
        # 3. 处理文本增量
        if delta.get("content"):
            await pipe.text_delta(delta["content"])

        # 4. 处理工具调用
        if delta.get("tool_calls"):
            yield {"event": "tool_call", "tool_call": {...}}

        # 5. 处理流结束
        if finish_reason:
            yield {"event": "final_content", ...}
```

### 4. 依赖注入层 (di/)

#### container.py

简单的依赖注入容器：

**ServiceContainer**：

```python
class ServiceContainer:
    def register(name, service)           # 注册服务实例
    def register_factory(name, factory)    # 注册服务工厂
    def get(name) -> Optional[Any]        # 获取服务实例
    def has(name) -> bool                 # 检查服务是否存在
    def remove(name)                      # 移除服务
    def clear()                           # 清空所有服务
```

**Injector**：

```python
class Injector:
    def inject(obj)                       # 注入匹配的服务
    def inject_with_annotations(obj)       # 基于类型注解注入
    def get_service(name) -> Optional[Any] # 获取服务
```

**核心服务**：

| 服务名 | 接口 | 功能 |
|--------|------|------|
| `query_wrapper` | QueryWrapper | 查询包装 |
| `tool_manager` | ToolManager | MCP 工具管理 |
| `memory_service` | MemoryService | 记忆服务 (mem0) |
| `prompt_service` | PromptService | PE 提示词服务 |
| `session_service` | SessionService | 会话服务 |

### 5. 上下文层 (context/)

#### context_maker.py

上下文构建器，采用并行流水线架构：

```python
class DefaultContextMaker:
    async def build_context(session_id, user_query, **kwargs):
        # 1. 获取或创建上下文
        context = get_context_manager().get_latest(...)

        # 2. 并行构建各组件
        results = await asyncio.gather(
            prompt_service.build_prompt(...),   # 系统提示词
            memory_service.search(query),       # RAG 检索
            tool_manager.get_tools(),          # 工具列表
            session_service.get_session(...)    # 会话状态
        )

        # 3. 更新上下文
        context.system_prompt = system_prompt
        context.messages.append({"role": "user", "content": user_query})
        context.tools = tools
        context.memory = rag_results

        # 4. 增强上下文
        await self.augment_context(context, **kwargs)
```

**上下文增强器 (Augmenters)**：

- `ScheduleAugmenter`: 日程表增强
- 可扩展的增强器机制

### 6. 基础设施层 (infrastructure/)

#### LLM Clients

**OpenAIStyleLLMClient**：

```python
class OpenAIStyleLLMClient:
    async def chat_completion(messages, model, temperature, max_tokens, tools):
        # 非流式调用
        response = await self.client.chat.completions.create(...)
        return response.model_dump()

    async def chat_completion_stream(messages, model, temperature, max_tokens, tools):
        # 流式调用
        stream = await self.client.chat.completions.create(stream=True, ...)
        async for chunk in stream:
            yield chunk.model_dump_json()
```

#### ProcessPipe

事件流管道，实现 Agent 和外部系统的异步通信：

```python
class ProcessPipe:
    # 文本输出
    async def text_delta(text: str)           # 文本增量
    async def final_text(text: str)           # 最终文本

    # 工具调用
    async def tool_call(name: str, arguments: Any)       # 工具调用
    async def tool_result(name: str, success: bool, result: Any)  # 工具结果

    # 审批流程
    async def approval_required(name, arguments, approval_id, message, safety_assessment)
    async def wait_for_approval(approval_id, timeout) -> str

    # 错误处理
    async def error(message: str)
    async def close(message: str | None = None)

    # 状态查询
    def is_closed() -> bool
    def is_cancelled() -> bool
```

**事件类型**：

| 类型 | 说明 |
|------|------|
| `text_delta` | 文本增量输出 |
| `tool_call` | 工具调用通知 |
| `tool_result` | 工具执行结果 |
| `final` | 最终输出 |
| `error` | 错误信息 |
| `approval_required` | 需要审批 |
| `approval_decision` | 审批决定 |
| `think_delta` | 思考过程输出 |

#### Handlers

**TTS Handler**：
- 文本转语音处理
- 音频流处理

**VRMA Handler**：
- VRM 动画处理
- 动作合成

### 7. 领域层 (domain/)

#### 数据模型

**AgentRequest**：

```python
@dataclass
class AgentRequest:
    session_id: str              # 会话 ID
    query: str                    # 用户查询
    agent_id: Optional[str] = None
    extraInfo: Dict[str, Any] = None
```

**Context**：

```python
class Context:
    session_id: str
    agent_id: str
    user_query: str
    system_prompt: str
    messages: List[Dict]
    tools: List[Dict]
    memory: Any
    schedule: Optional[str]
```

#### 事件类型

```python
class ClientEventType(Enum):
    USER_MESSAGE = "user_message"
    TOOL_APPROVAL = "tool_approval"
    HEARTBEAT = "heartbeat"
    INIT_SESSION = "init_session"
    ATTACH_SESSION = "attach_session"
    DETACH_SESSION = "detach_session"
    DELETE_SESSION = "delete_session"
```

## 数据流

### 请求处理流程

```
1. 客户端发送 WebSocket 消息
   │
   ├─→ POST /api/agent/profile (Agent 配置)
   └─→ WS /ws/agent (实时通信)
        │
        ↓
2. FastAPI 接收并解析消息
   │
   └─→ SessionOrchestrator.handle_client_message()
        │
        ↓
3. 会话编排器路由到 AgentCoordinator
   │
   └─→ AgentCoordinator.process()
        │
        ↓
4. AgentCoordinator 选择合适的 Agent
   │
   ├─→ 如果指定 agent_id，直接使用
   ├─→ 否则使用 TaskDispatcher 选择
   └─→ 默认使用第一个注册的 Agent
        │
        ↓
5. Agent 处理请求
   │
   ├─→ ContextMaker.build_context()
   │    │
   │    ├─→ prompt_service.build_prompt()      → 系统提示词
   │    ├─→ memory_service.search(query)       → RAG 检索
   │    ├─→ tool_manager.get_tools()            → 工具列表
   │    └─→ session_service.get_session()      → 会话状态
   │
   ├─→ Agent.run_with_tools() / Agent.process()
   │    │
   │    ├─→ LLM.chat_completion_stream()
   │    │    │
   │    │    ├─→ 文本生成 → pipe.text_delta()
   │    │    │
   │    │    └─→ 工具调用 → pipe.tool_call()
   │    │         │
   │    │         ├─→ tool_manager.call_tool()
   │    │         │    │
   │    │         │    ├─→ 执行工具
   │    │         │    └─→ 返回结果
   │    │         │
   │    │         ├─→ 如果需要审批 → pipe.approval_required()
   │    │         │    └─→ pipe.wait_for_approval()
   │    │         │
   │    │         └─→ pipe.tool_result()
   │    │
   │    └─→ 最终结果 → pipe.final_text()
   │
   └─→ MemoryAwareAgent.memory_hook()
        │
        └─→ memory_service.add()
        │
   ↓
6. TTS/VRMA 处理输出
   │
   ├─→ TTS Handler → 语音合成
   └─→ VRMA Handler → 动作合成
        │
   ↓
7. WebSocket 推送到客户端
```

## 配置管理

### 配置文件

| 文件 | 说明 |
|------|------|
| `config/core.json` | 核心服务配置 |
| `config/mcp_servers.json` | MCP 服务器配置 |
| `config/mem0.json` | 记忆服务配置 |
| `config/tts.json` | TTS 引擎配置 |
| `config/motion.json` | 动作配置 |
| `config/pe.json` | PE 服务配置 |
| `core_config.json` | 全局核心配置 |

### 环境要求

- Python 3.10+
- Node.js (前端依赖)
- API Keys 配置在 `api.key` 文件

### API Key 配置

创建 `api.key` 文件：

```json
{
    "openapi_key": "your-api-key"
}
```

## 启动方式

### 一键启动

```bash
python run_all.py
```

### 分别启动

```bash
# 1. 启动 MCP Hub
python run_all.py  # 或单独启动 MCP Hub

# 2. 启动 PE Server
python run_all.py  # 或单独启动 PE Server

# 3. 启动主服务
python -m src.main.back_end

# 4. 启动前端
cd webUI
npm install
npm run dev
```

### 服务端口

| 服务 | 地址 |
|------|------|
| 主服务 | `http://localhost:8000` |
| 前端界面 | `http://localhost:5174` |
| MCP Hub | `http://localhost:9000` |
| PE Server | `http://localhost:8001` |

## 关键技术特点

### 1. 异步流式处理

- 全程使用 `async/await`
- LLM 流式响应实时推送
- WebSocket 双向通信
- asyncio 并行任务处理

```python
# 并行构建上下文
results = await asyncio.gather(
    prompt_service.build_prompt(),
    memory_service.search(query),
    tool_manager.get_tools(),
    session_service.get_session(),
    return_exceptions=True
)
```

### 2. 工具调用框架

- 支持 MCP (Model Context Protocol) 协议
- 工具调用审批机制
- ReAct 模式循环执行
- 工具调用次数限制（防死循环）

```python
# ReAct 循环
for step in range(max_steps):
    async for event in run_llm_with_tools(llm_client, context):
        if event["event"] == "tool_call":
            result = await tool_manager.call_tool(call)
            if result.get("status") == "pending":
                await pipe.approval_required(...)
                decision = await pipe.wait_for_approval(...)
```

### 3. 记忆系统

- RAG 检索增强生成
- mem0ai 长期记忆
- 会话状态管理
- 记忆自动添加

```python
# RAG 检索
rag_results = await memory_service.search(
    query=user_query,
    user_id=session_id,
    limit=5
)
```

### 4. 可扩展架构

- 依赖注入容器
- 工厂模式创建对象
- 插件化设计
- 配置文件驱动

```python
# 服务注册
container.register("query_wrapper", DefaultQueryWrapper())
container.register_factory("tool_manager", McpToolManager)

# Agent 工厂
agent = AgentFactory.create_agent(agent_profile)
```

### 5. 多模态输出

- TTS 文本转语音
- VRMA 虚拟动作
- 弹幕互动系统
- Bilibili 直播集成

## Agent Profile 配置

### 基本配置

```json
{
    "agent_id": "agent_identifier",
    "name": "Agent Name",
    "avatar_url": "https://example.com/avatar.png"
}
```

### LLM 配置

```json
{
    "backbone_llm_config": {
        "provider": "openai",
        "openapi_url": "https://api.openai.com/v1",
        "openapi_key": "your-api-key",
        "model_name": "gpt-4",
        "temperature": 0.7,
        "max_tokens": 2000,
        "timeout": 30
    }
}
```

### 行为配置

```json
{
    "behavior": {
        "max_tool_calls": 5,
        "approval_required": ["dangerous_tools"],
        "system_prompt": "You are a helpful AI assistant."
    }
}
```

### 增强器配置

```json
{
    "augmenters": [
        "schedule_augmenter"
    ]
}
```

### 完整示例

```json
{
    "agent_id": "fast_agent",
    "name": "Fast Agent",
    "avatar_url": "https://example.com/fast_agent.png",
    "backbone_llm_config": {
        "provider": "openai",
        "openapi_url": "https://api.openai.com/v1",
        "openapi_key": "",
        "model_name": "gpt-4",
        "temperature": 0.7,
        "max_tokens": 4096
    },
    "behavior": {
        "max_tool_calls": 5
    },
    "augmenters": [
        {
            "name": "schedule_augmenter",
            "params": {}
        }
    ]
}
```

## 扩展开发指南

### 添加新服务

1. **定义接口** (`di/services/interfaces/`)

```python
from abc import ABC, abstractmethod

class NewServiceInterface(ABC):
    @abstractmethod
    async def do_something(self, data: Dict) -> Any:
        pass
```

2. **实现服务** (`di/services/impl/`)

```python
class NewService(NewServiceInterface):
    async def do_something(self, data: Dict) -> Any:
        # 实现逻辑
        return result
```

3. **注册服务** (`back_end.py`)

```python
from src.di.container import get_service_container
from src.di.services.impl.new_service import NewService

container = get_service_container()
container.register("new_service", NewService())
```

### 添加新 Agent

1. **继承 BaseAgent** (`agent/base_agents.py`)

```python
from src.agent.abs_agent import BaseAgent

class CustomAgent(BaseAgent):
    def __init__(self, agent_profile, name):
        super().__init__(agent_profile, name, ...)
        # 初始化逻辑

    async def initialize(self):
        # 初始化逻辑
        pass

    async def process(self, request, pipe: ProcessPipe):
        # 处理逻辑
        pass

    def get_capabilities(self):
        return {
            "type": "custom",
            "description": "Custom agent"
        }

    def estimate_cost(self, request):
        return {"time": 1000, "tokens": 100}
```

2. **在工厂中注册** (`agent/agent_factory.py`)

```python
class AgentFactory:
    @staticmethod
    def create_agent(profile):
        agent_type = profile.get("type", "base")
        if agent_type == "custom":
            return CustomAgent(profile, name=...)
        # ...
```

### 添加新工具 (MCP)

1. **实现 MCP Server**

```python
from mcp.server import Server

app = Server("my_tool")

@app.list_tools()
async def list_tools():
    return [
        {
            "name": "my_tool",
            "description": "My custom tool",
            "inputSchema": {
                "type": "object",
                "properties": {...}
            }
        }
    ]

@app.call_tool()
async def call_tool(name, arguments):
    if name == "my_tool":
        # 执行工具逻辑
        return result
```

2. **配置 MCP Server** (`config/mcp_servers.json`)

```json
{
    "servers": [
        {
            "name": "my_tool_server",
            "command": "python",
            "args": ["/path/to/mcp_server.py"],
            "env": {}
        }
    ]
}
```

### 添加上下文增强器

1. **实现增强器** (`context/augmenters.py`)

```python
class CustomAugmenter:
    def __init__(self, params):
        self.params = params

    async def augment(self, context, **kwargs):
        # 增强逻辑
        context.custom_field = ...
        return context

def create_augmenter(name, params):
    if name == "custom_augmenter":
        return CustomAugmenter(params)
    return None
```

2. **配置增强器** (`agent_profile.json`)

```json
{
    "augmenters": [
        {
            "name": "custom_augmenter",
            "params": {...}
        }
    ]
}
```

## RoadMap

- [x] 重构项目目录结构，提升模块化程度
- [x] 整合 MCP Hub 工具管理
- [ ] 接入视觉能力
- [ ] Agent 路由化

---

*文档生成时间: 2026-02-13*
*项目版本: 1.0.0*
