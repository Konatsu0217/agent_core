# Agent Core 开发完整指南

## 📋 目录
- [项目结构](#项目结构)
- [开发顺序建议](#开发顺序建议)
- [Planning 核心知识](#planning-核心知识)
- [详细实现指南](#详细实现指南)
- [推荐学习资源](#推荐学习资源)

---

## 🗂️ 项目结构

```
agent_core/
├── main.py                      # 入口文件，启动 FastAPI 服务
├── config.py                    # 配置加载模块
├── requirements.txt             # 依赖列表
├── README.md                    # 项目说明
│
├── core/                        # 核心模块
│   ├── __init__.py
│   ├── orchestrator.py          # 🔥 调度器（核心）
│   ├── event_router.py          # 🔥 事件路由（Planning）
│   ├── protocol_driver.py       # 协议驱动器
│   └── request_tracker.py       # 请求追踪器
│
├── clients/                     # 外部服务客户端
│   ├── __init__.py
│   ├── llm_client.py            # 🔥 LLM 客户端
│   ├── pe_client.py             # PE Server 客户端
│   ├── mcp_client.py            # MCP Hub 客户端
│   └── session_client.py        # Session Manager 客户端
│
├── models/                      # 数据模型
│   ├── __init__.py
│   ├── agent_request.py         # 请求模型
│   ├── agent_response.py        # 响应模型
│   ├── agent_settings.py        # 配置模型
│   └── protocol_message.py      # 协议消息模型
│
├── handlers/                    # 特殊处理器
│   ├── __init__.py
│   ├── tool_call_handler.py     # 🔥 工具调用处理器
│   └── streaming_handler.py     # 流式响应处理器
│
├── utils/                       # 工具函数
│   ├── __init__.py
│   ├── logger.py                # 日志配置
│   ├── retry.py                 # 重试装饰器
│   └── token_counter.py         # Token 估算
│
└── tests/                       # 测试文件
    ├── test_orchestrator.py
    ├── test_llm_client.py
    └── test_tool_calls.py
```

---

## 🚀 开发顺序建议

### Phase 0: 环境搭建（预计 0.5 天）
- [ ] 创建项目结构
- [ ] 配置 `requirements.txt`
- [ ] 设置日志系统
- [ ] 写基础配置加载

**输出**: 项目骨架 + 配置文件加载成功

---

### Phase 1: 基础客户端（预计 1-2 天）

#### 1.1 实现 `models/` 数据模型
**文件**: `models/agent_settings.py`, `models/agent_request.py`, `models/agent_response.py`

**任务**:
- [ ] 定义 `AgentSettings` (Pydantic 模型)
- [ ] 定义 `AgentRequest` (包含 request_id, session_id, user_query)
- [ ] 定义 `AgentResponse` (包含 text_output, protocol_messages)

**验证**: 能成功序列化/反序列化 JSON

---

#### 1.2 实现 `clients/llm_client.py`
**核心方法**:
```python
class LLMClient:
    async def chat_completion(self, messages: list, tools: list = None, **kwargs) -> dict
    async def _make_request(self, payload: dict) -> dict
```

**任务**:
- [ ] 实现基础 HTTP POST 请求（用 `httpx.AsyncClient`）
- [ ] 添加错误处理（超时、网络错误）
- [ ] 添加简单重试逻辑（用 `tenacity`）

**验证**: 能成功调用 OpenAI API 并返回响应

---

#### 1.3 实现 `clients/pe_client.py`
**核心方法**:
```python
class PEClient:
    async def build_request(self, session_id: str, user_query: str) -> dict
```

**任务**:
- [ ] 调用 PE Server 的 `/pe/build_request` 接口
- [ ] 解析返回的 `llm_request` 字段

**验证**: 能拿到包含 messages 和 tools 的完整请求体

---

### Phase 2: 简单调度流程（预计 1-2 天）

#### 2.1 实现 `core/orchestrator.py`（简化版）
**核心方法**:
```python
class AgentOrchestrator:
    async def process_query(self, request: AgentRequest) -> AgentResponse
    async def _call_pe(self, request: AgentRequest) -> dict
    async def _call_llm(self, llm_request: dict) -> dict
```

**任务**:
- [ ] 实现最简单的流程: `query -> PE -> LLM -> response`
- [ ] 暂时不处理工具调用
- [ ] 生成 request_id (用 `uuid.uuid4()`)

**验证**: 用户输入 -> 返回 LLM 文本输出

---

#### 2.2 实现 `main.py` FastAPI 接口
**接口**:
```python
@app.post("/agent/query")
async def handle_query(request: AgentRequest) -> AgentResponse
```

**任务**:
- [ ] 暴露 HTTP 接口
- [ ] 调用 `AgentOrchestrator.process_query()`

**验证**: `curl` 测试能返回正确响应

---

### Phase 3: Planning 与路由（预计 2-3 天）⚠️ 重点

#### 3.1 学习 Planning 基础知识
**必读内容**:
1. ReAct 论文: [Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)
2. LangChain Agent 文档: [Agent Concepts](https://python.langchain.com/docs/modules/agents/)
3. Function Calling 文档: [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling)

**核心概念**:
- **ReAct 模式**: Reason (思考) -> Act (行动) -> Observe (观察) 循环
- **Planning 策略**: 
  - Zero-shot ReAct: LLM 自主决定每一步
  - Plan-and-Execute: 先规划所有步骤，再执行
  - Reflexion: 执行后反思并调整计划

---

#### 3.2 实现 `core/event_router.py`
**核心方法**:
```python
class EventRouter:
    async def route(self, request: AgentRequest) -> ExecutionPlan
    def _analyze_query(self, query: str) -> QueryIntent
    def _build_plan(self, intent: QueryIntent, settings: AgentSettings) -> ExecutionPlan
```

**任务**:
- [ ] 实现简单的规则路由（基于关键词或配置）
- [ ] 返回执行计划（哪些模块启用、参数如何传递）

**示例逻辑**:
```python
# 简单策略
if "搜索" in query or "查询" in query:
    plan.use_tools = True
if settings.enable_rag and "知识" in query:
    plan.use_rag = True
```

**验证**: 不同类型的 query 返回不同的执行计划

---

#### 3.3 （可选）实现 LLM-based Planning
**进阶方法**:
```python
async def _llm_plan(self, query: str) -> ExecutionPlan:
    """用 LLM 分析 query，生成执行计划"""
    planning_prompt = f"""
    分析以下用户请求，决定需要哪些工具:
    Query: {query}
    
    可用工具: [搜索, RAG, 计算器]
    请以 JSON 格式返回: {{"tools": [...], "reasoning": "..."}}
    """
    # 调用 LLM 生成 JSON 计划
```

**任务**:
- [ ] 设计 planning prompt
- [ ] 解析 LLM 返回的 JSON 计划

---

### Phase 4: 工具调用与多轮对话（预计 3-4 天）⚠️ 最难

#### 4.1 理解 Function Calling 流程
**标准流程**:
```
1. User Query -> LLM (with tools)
2. LLM 返回: tool_calls = [{"name": "search", "arguments": {"query": "..."}}]
3. 执行工具: result = execute_tool("search", {"query": "..."})
4. 将结果作为 tool message 再次发给 LLM
5. LLM 基于工具结果生成最终答案
```

**关键点**:
- Messages 数组格式: `[user, assistant(with tool_calls), tool, assistant]`
- 可能需要多轮工具调用（LLM 可能连续调用多个工具）

---

#### 4.2 实现 `handlers/tool_call_handler.py`
**核心方法**:
```python
class ToolCallHandler:
    async def handle_tool_calls(
        self, 
        messages: list,  # 当前对话历史
        tool_calls: list,  # LLM 返回的工具调用
        max_iterations: int = 5
    ) -> dict:
        """处理工具调用的完整循环"""
```

**任务**:
- [ ] 解析 LLM 返回的 `tool_calls` 字段
- [ ] 调用 MCP Hub 执行工具
- [ ] 构造 tool message 并追加到 messages
- [ ] 再次调用 LLM
- [ ] 循环直到 LLM 不再请求工具或达到最大次数

**伪代码**:
```python
async def handle_tool_calls(self, messages, tool_calls, max_iter=5):
    for iteration in range(max_iter):
        # 1. 执行所有工具调用
        tool_results = await self._execute_tools(tool_calls)
        
        # 2. 构造 tool messages
        for call, result in zip(tool_calls, tool_results):
            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": json.dumps(result)
            })
        
        # 3. 再次调用 LLM
        response = await self.llm_client.chat_completion(messages)
        
        # 4. 检查是否还有工具调用
        if not response.get("tool_calls"):
            return response  # 完成
        
        tool_calls = response["tool_calls"]  # 继续下一轮
    
    raise MaxIterationError("超过最大工具调用次数")
```

**验证**: 测试需要多步工具的 query（如"搜索天气，然后设置提醒"）

---

#### 4.3 更新 `core/orchestrator.py` 支持工具调用
**任务**:
- [ ] 在 `process_query()` 中检测 `tool_calls`
- [ ] 调用 `ToolCallHandler.handle_tool_calls()`

---

### Phase 5: 协议驱动与玩法集成（预计 1-2 天）

#### 5.1 实现 `core/protocol_driver.py`
**核心方法**:
```python
class ProtocolDriver:
    async def parse(self, llm_response: dict) -> List[ProtocolMessage]
    def _extract_tts_commands(self, text: str) -> List[TTSMessage]
    def _extract_vrm_commands(self, text: str) -> List[VRMMessage]
```

**任务**:
- [ ] 定义协议格式（如 `[TTS:文本]`）
- [ ] 用正则表达式提取指令
- [ ] 生成标准化的 `ProtocolMessage`

**示例**:
```python
# LLM 返回: "好的！[TTS:你好，我是AI助手]"
# 解析为: ProtocolMessage(type="tts", content="你好，我是AI助手", config={...})
```

---

#### 5.2 集成到 `orchestrator.py`
**任务**:
- [ ] 在 `process_query()` 末尾调用 `protocol_driver.parse()`
- [ ] 将 protocol_messages 添加到 `AgentResponse`

---

### Phase 6: 会话管理集成（预计 1 天）

#### 6.1 实现 `clients/session_client.py`
**核心方法**:
```python
class SessionClient:
    async def save_message(self, session_id: str, role: str, content: str)
    async def get_history(self, session_id: str, limit: int = 10) -> list
```

**任务**:
- [ ] 调用 Session Manager 的保存接口
- [ ] 在 `orchestrator.py` 中调用保存

---

### Phase 7: 优化与监控（预计 1-2 天）

#### 7.1 实现 `core/request_tracker.py`
**任务**:
- [ ] 为每个请求生成 `request_id` 和 `trace_id`
- [ ] 记录请求开始/结束时间
- [ ] 统计 token 消耗

#### 7.2 实现 `utils/logger.py`
**任务**:
- [ ] 配置 `structlog`
- [ ] 所有日志包含 `request_id`

#### 7.3 添加错误处理
**任务**:
- [ ] 统一的异常类（`AgentException`）
- [ ] 超时处理
- [ ] 重试机制（`tenacity`）

---

## 🧠 Planning 核心知识补充

### 1. ReAct 模式（推荐阅读）

**核心思想**: LLM 通过"思考-行动-观察"循环解决复杂任务

**流程示例**:
```
User: 今天北京天气怎么样？明天适合户外运动吗？

Thought 1: 我需要先查询北京今天的天气
Action 1: search_weather(city="北京", date="today")
Observation 1: 今天北京晴，25°C

Thought 2: 现在我需要查询明天的天气来判断是否适合户外
Action 2: search_weather(city="北京", date="tomorrow")
Observation 2: 明天北京多云，20-28°C，风力3级

Thought 3: 根据天气信息，我可以给出建议了
Answer: 今天北京天气晴朗，25°C。明天多云，20-28°C，风力较小，非常适合户外运动！
```

**实现要点**:
- LLM 需要在 prompt 中被引导使用 Thought/Action/Observation 格式
- 你的 `ToolCallHandler` 就是在实现这个循环
- OpenAI 的 Function Calling 是简化版的 ReAct（隐藏了 Thought）

---

### 2. Planning 策略对比

| 策略 | 特点 | 适用场景 | 实现难度 |
|------|------|----------|----------|
| **规则路由** | 基于关键词/配置决策 | 简单任务、固定流程 | ⭐ 简单 |
| **Zero-shot ReAct** | LLM 自主决定每一步 | 复杂推理任务 | ⭐⭐ 中等 |
| **Plan-and-Execute** | 先生成完整计划再执行 | 多步骤任务、需要优化执行顺序 | ⭐⭐⭐ 较难 |
| **Reflexion** | 执行后反思并重新规划 | 需要纠错的任务 | ⭐⭐⭐⭐ 困难 |

**我的建议**:
- Phase 3 先实现**规则路由**（快速上线）
- Phase 4 实现 **Zero-shot ReAct**（通过 Function Calling）
- 后续有需要再升级到 Plan-and-Execute

---

### 3. Function Calling 详解

**OpenAI 的 tools 参数格式**:
```json
{
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_weather",
        "description": "获取指定城市的天气",
        "parameters": {
          "type": "object",
          "properties": {
            "city": {"type": "string", "description": "城市名称"},
            "date": {"type": "string", "enum": ["today", "tomorrow"]}
          },
          "required": ["city"]
        }
      }
    }
  ]
}
```

**LLM 返回的 tool_calls 格式**:
```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": null,
      "tool_calls": [
        {
          "id": "call_abc123",
          "type": "function",
          "function": {
            "name": "get_weather",
            "arguments": "{\"city\": \"北京\", \"date\": \"today\"}"
          }
        }
      ]
    }
  }]
}
```

**你需要做的**:
1. 从 PE Server 或 MCP Hub 获取 tools 列表
2. 传递给 LLM
3. 解析返回的 `tool_calls`
4. 调用实际工具
5. 把结果作为 tool message 再发给 LLM

---

### 4. Messages 数组的正确构造

**完整的工具调用对话示例**:
```python
messages = [
    {"role": "system", "content": "你是一个有用的助手"},
    {"role": "user", "content": "北京明天天气怎么样？"},
    
    # LLM 第一次响应（决定调用工具）
    {
        "role": "assistant",
        "content": null,
        "tool_calls": [{
            "id": "call_1",
            "type": "function",
            "function": {"name": "get_weather", "arguments": "{\"city\":\"北京\"}"}
        }]
    },
    
    # 工具执行结果
    {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": "{\"temperature\": 25, \"condition\": \"晴\"}"
    },
    
    # LLM 第二次响应（基于工具结果生成最终答案）
    {
        "role": "assistant",
        "content": "北京明天天气晴朗，气温25°C，适合出行！"
    }
]
```

**关键点**:
- 必须保留 `tool_calls` 字段（即使为空）
- `tool_call_id` 必须匹配
- `content` 必须是字符串（通常 JSON 化工具结果）

---

## 📚 推荐学习资源

### 必读论文
1. **ReAct**: [Synergizing Reasoning and Acting](https://arxiv.org/abs/2210.03629)
   - 核心论文，理解 Agent 的基础
2. **Reflexion**: [Language Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366)
   - 理解如何让 Agent 自我反思

### 必读文档
1. **OpenAI Function Calling**: https://platform.openai.com/docs/guides/function-calling
2. **LangChain Agents**: https://python.langchain.com/docs/modules/agents/
3. **Anthropic Tools**: https://docs.anthropic.com/claude/docs/tool-use

### 推荐开源项目
1. **LangChain**: https://github.com/langchain-ai/langchain
   - 看 `langchain/agents/` 目录
2. **AutoGPT**: https://github.com/Significant-Gravitas/AutoGPT
   - 理解多步骤规划
3. **GPT-Engineer**: https://github.com/gpt-engineer-org/gpt-engineer
   - 看代码生成的 planning 策略

### Python 异步编程
1. **Real Python 教程**: https://realpython.com/async-io-python/
2. **httpx 文档**: https://www.python-httpx.org/async/
3. **tenacity 重试**: https://tenacity.readthedocs.io/

---

## 🛠️ 依赖清单 (requirements.txt)

```txt
# Web 框架
fastapi==0.104.1
uvicorn[standard]==0.24.0

# 异步 HTTP 客户端
httpx==0.25.1
aiohttp==3.9.0

# 数据验证
pydantic==2.5.0
pydantic-settings==2.1.0

# 重试与错误处理
tenacity==8.2.3

# 日志
structlog==23.2.0

# 性能优化
uvloop==0.19.0

# Token 估算
tiktoken==0.5.1

# 工具
python-dotenv==1.0.0
```

---

## 🎯 最小可运行示例（MVP 代码）

### `main.py`
```python
from fastapi import FastAPI
from models.agent_request import AgentRequest
from models.agent_response import AgentResponse
from core.orchestrator import AgentOrchestrator
from config import load_settings

app = FastAPI()
settings = load_settings()
orchestrator = AgentOrchestrator(settings)

@app.post("/agent/query")
async def handle_query(request: AgentRequest) -> AgentResponse:
    return await orchestrator.process_query(request)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
```

### 测试命令
```bash
curl -X POST http://localhost:8080/agent/query \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test_123",
    "user_query": "什么是机器学习？"
  }'
```

---

## ✅ 每个阶段的验证标准

| Phase | 验证标准 | 预期结果 |
|-------|---------|---------|
| Phase 1 | 调用 LLM API | 返回文本响应 |
| Phase 2 | 完整流程测试 | query -> 返回 AgentResponse |
| Phase 3 | 不同 query 的路由 | 不同类型返回不同执行计划 |
| Phase 4 | 工具调用测试 | "搜索天气"能触发工具并返回结果 |
| Phase 5 | 协议解析测试 | LLM 返回 `[TTS:xxx]` 能解析出 protocol_message |
| Phase 6 | 会话历史测试 | 第二轮对话能看到第一轮历史 |

---

## 🐛 常见问题预警

### 1. Function Calling 常见错误
- ❌ 忘记在 messages 中保留 `tool_calls` 字段
- ❌ `tool_call_id` 不匹配
- ❌ tool message 的 `content` 不是字符串

### 2. 异步编程常见错误
- ❌ 忘记 `await` 导致返回 coroutine 对象
- ❌ 在同步代码中调用异步函数
- ❌ 连接池未复用导致性能问题

### 3. 工具调用死循环
- ❌ 没有设置 `max_iterations`
- ❌ LLM 一直请求同一个工具但参数错误

---

## 📝 开发时间估算

| Phase | 预计时间 | 累计时间 |
|-------|---------|---------|
| Phase 0 | 0.5 天 | 0.5 天 |
| Phase 1 | 1.5 天 | 2 天 |
| Phase 2 | 1.5 天 | 3.5 天 |
| Phase 3 | 2.5 天 | 6 天 |
| Phase 4 | 3.5 天 | 9.5 天 |
| Phase 5 | 1.5 天 | 11 天 |
| Phase 6 | 1 天 | 12 天 |
| Phase 7 | 1.5 天 | 13.5 天 |

**总计**: 约 **2-3 周**（全职开发）

---

## 🚀 下一步行动

1. [ ] 阅读 ReAct 论文（1 小时）
2. [ ] 阅读 OpenAI Function Calling 文档（30 分钟）
3. [ ] 创建项目结构（30 分钟）
4. [ ] 开始 Phase 1: 实现数据模型和 LLMClient

**遇到问题随时回来找我！Good luck! 💪**
