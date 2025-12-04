# Agent 范式深度解析：从 ReAct 到实战

## 📖 目录
1. [什么是 Agent？](#什么是-agent)
2. [核心范式对比](#核心范式对比)
3. [ReAct 深度解析](#react-深度解析)
4. [其他主流范式](#其他主流范式)
5. [如何选择范式](#如何选择范式)
6. [在你的 Agent Core 中应用](#在你的-agent-core-中应用)

---

## 🤖 什么是 Agent？

### 定义
**Agent** = LLM + Planning + Tools + Memory

```
┌─────────────────────────────────────┐
│              Agent                  │
├─────────────────────────────────────┤
│  ┌──────────┐   ┌──────────────┐   │
│  │   LLM    │   │   Planning   │   │
│  │  (大脑)  │◄──┤  (决策引擎)   │   │
│  └─────┬────┘   └──────────────┘   │
│        │                            │
│        ▼                            │
│  ┌──────────┐   ┌──────────────┐   │
│  │  Tools   │   │    Memory    │   │
│  │  (工具)  │   │   (记忆)     │   │
│  └──────────┘   └──────────────┘   │
└─────────────────────────────────────┘
```

### 与普通 LLM 调用的区别

| 特性 | 普通 LLM | Agent |
|------|---------|-------|
| 交互方式 | 单次问答 | 多轮推理 |
| 工具使用 | 无 | 可调用外部工具 |
| 决策能力 | 无 | 自主规划步骤 |
| 复杂任务 | 难以处理 | 分步解决 |

**示例对比**:
```
❌ 普通 LLM:
User: "帮我订明天去上海的机票"
LLM: "抱歉，我无法直接订票，你可以去携程..."

✅ Agent:
User: "帮我订明天去上海的机票"
Agent Thought: 我需要先查询航班信息
Agent Action: search_flights(from="北京", to="上海", date="2024-01-15")
Agent Observation: [航班列表]
Agent Thought: 用户未指定偏好，我应该询问
Agent: "找到3个航班，你偏好早班机还是晚班机？"
```

---

## 🎭 核心范式对比

### 范式全景图

```
Agent 范式
├── Chain-based (链式)
│   ├── Simple Chain: A → B → C
│   └── Sequential Chain: 固定步骤序列
│
├── ReAct (推理-行动)
│   ├── Zero-shot ReAct: LLM 自主决策每一步
│   └── Few-shot ReAct: 提供示例引导
│
├── Plan-and-Execute (先规划后执行)
│   ├── Planning: 生成完整计划
│   └── Execution: 按计划执行
│
├── Reflexion (反思)
│   ├── Execute: 执行任务
│   ├── Reflect: 反思结果
│   └── Refine: 改进计划
│
└── Tree-based (树状搜索)
    ├── Tree of Thoughts: 探索多条路径
    └── Best-first Search: 优先最优路径
```

---

## 🔥 ReAct 深度解析

### 核心思想

**ReAct** = **Re**asoning (推理) + **Act**ing (行动)

LLM 通过交替进行"思考"和"行动"来解决复杂任务。

### 完整流程图

```
┌─────────────────────────────────────────────┐
│            ReAct 循环                        │
└─────────────────────────────────────────────┘
              │
              ▼
    ┌─────────────────┐
    │  Thought (思考)  │ ← LLM 分析当前状态
    │ "我需要先查天气" │    决定下一步做什么
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │  Action (行动)   │ ← 调用具体工具
    │ search_weather() │    执行操作
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │Observation(观察) │ ← 获取工具返回结果
    │ "今天25°C晴"     │
    └────────┬────────┘
             │
             ▼
         是否完成? ──No──┐
             │           │
            Yes          │
             │           │
             ▼           │
         ┌────────┐     │
         │ Answer │     │
         └────────┘     │
                        │
         ◄──────────────┘
        (回到 Thought)
```

### 详细示例

**任务**: "明天北京适合户外运动吗？"

```
=== 第 1 轮 ===

Thought 1: 要判断是否适合户外运动，我需要先知道明天北京的天气情况，
           包括温度、降水和风力。

Action 1: search_weather(city="北京", date="tomorrow")

Observation 1: {
  "temperature": "18-25°C",
  "weather": "多云",
  "wind": "3级",
  "precipitation": "10%"
}

=== 第 2 轮 ===

Thought 2: 天气数据显示明天多云，温度适宜，风力较小，降水概率低。
           但我还需要考虑空气质量，这对户外运动很重要。

Action 2: get_air_quality(city="北京", date="tomorrow")

Observation 2: {
  "aqi": 85,
  "level": "良",
  "pm25": 60
}

=== 第 3 轮 ===

Thought 3: 空气质量为良，AQI 85，虽然不是优但可以接受。
           现在我有足够信息给出建议了。

Answer: 明天北京的天气条件总体适合户外运动：
        - 温度 18-25°C，体感舒适
        - 多云天气，不会太热
        - 风力 3 级，较为平缓
        - 降水概率仅 10%
        - 空气质量为良（AQI 85）
        
        建议在上午或傍晚进行户外活动，避开中午时段。
```

### ReAct Prompt 设计

**标准 Prompt 模板**:
```
You run in a loop of Thought, Action, Observation.
At the end of the loop you output an Answer.

Use Thought to describe your thinking about the question.
Use Action to run one of the actions available to you.
Observation will be the result of running those actions.

Available actions:
- search_weather(city: str, date: str): Get weather information
- get_air_quality(city: str): Get air quality index

Example:
Question: What's the weather in Beijing?
Thought: I need to search for Beijing's weather
Action: search_weather(city="Beijing", date="today")
Observation: Temperature: 25°C, Sunny
Thought: I now have the weather information
Answer: The weather in Beijing is sunny, 25°C

Now solve this:
Question: {user_question}
```

### OpenAI Function Calling 的 ReAct 简化版

OpenAI 的 Function Calling **隐藏了显式的 Thought**，直接返回 Action：

```python
# 传统 ReAct 需要解析文本
response = """
Thought: I need to check weather
Action: search_weather(city="Beijing")
"""

# OpenAI Function Calling 直接返回结构化
response = {
  "tool_calls": [{
    "function": {
      "name": "search_weather",
      "arguments": '{"city": "Beijing"}'
    }
  }]
}
```

**对比**:
| 特性 | 传统 ReAct | Function Calling |
|------|-----------|------------------|
| 思考过程 | 显式（Thought） | 隐式（内部推理） |
| 输出格式 | 文本解析 | 结构化 JSON |
| 可靠性 | 依赖 prompt | API 保证格式 |
| 可解释性 | 高（能看到思考） | 低（黑盒） |

---

## 🌟 其他主流范式

### 1. Plan-and-Execute (先规划后执行)

**核心思想**: 先用 LLM 生成完整计划，再按计划执行

**流程**:
```
Step 1: Planning Phase
┌──────────────────────────────────┐
│ User: "帮我准备明天的会议"        │
│                                  │
│ LLM Planning:                    │
│ 1. 查询日历确认会议时间           │
│ 2. 检查参会人员名单               │
│ 3. 准备会议资料                  │
│ 4. 发送会议提醒                  │
└──────────────────────────────────┘

Step 2: Execution Phase
执行每个步骤 → 收集结果 → 汇总反馈
```

**适用场景**:
- ✅ 多步骤任务需要整体优化
- ✅ 步骤之间有依赖关系
- ❌ 任务动态性强（计划容易失效）

**代码示例**:
```python
async def plan_and_execute(query: str):
    # Phase 1: Planning
    plan_prompt = f"""
    Create a step-by-step plan to accomplish:
    {query}
    
    Return as JSON: {{"steps": ["step1", "step2", ...]}}
    """
    plan = await llm.chat(plan_prompt)
    steps = json.loads(plan)["steps"]
    
    # Phase 2: Execution
    results = []
    for step in steps:
        result = await execute_step(step)
        results.append(result)
    
    # Phase 3: Synthesis
    return synthesize_results(results)
```

---

### 2. Reflexion (反思)

**核心思想**: 执行 → 评估 → 反思 → 改进

**流程**:
```
┌─────────────┐
│   Execute   │ → 执行任务
└──────┬──────┘
       ▼
┌─────────────┐
│   Evaluate  │ → 评估结果质量
└──────┬──────┘
       ▼
┌─────────────┐
│   Reflect   │ → 分析失败原因
└──────┬──────┘
       ▼
┌─────────────┐
│   Refine    │ → 改进策略
└──────┬──────┘
       │
       └──────► 重新执行
```

**完整示例**:

```
Task: 写一个 Python 排序函数

=== Iteration 1 ===
Execute: 
def sort(arr):
    return sorted(arr)

Evaluate: 太简单了，没有展示算法理解

Reflect: 
- 我直接用了内置函数
- 应该实现一个经典排序算法
- 用户可能想看算法细节

Refine: 重写为快速排序实现

=== Iteration 2 ===
Execute:
def quicksort(arr):
    if len(arr) <= 1: return arr
    pivot = arr[0]
    left = [x for x in arr[1:] if x < pivot]
    right = [x for x in arr[1:] if x >= pivot]
    return quicksort(left) + [pivot] + quicksort(right)

Evaluate: 算法正确，但效率可以优化

Reflect:
- 选择第一个元素作为 pivot 在最坏情况下是 O(n²)
- 应该使用随机 pivot

Refine: 添加随机 pivot 选择

=== Final Result ===
(优化后的快速排序实现)
```

**适用场景**:
- ✅ 需要高质量输出（代码生成、写作）
- ✅ 有明确评估标准
- ❌ 简单任务（反思成本高）

---

### 3. Tree of Thoughts (思维树)

**核心思想**: 探索多条推理路径，选择最优解

```
                  根问题
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
      路径A        路径B        路径C
        │           │           │
    ┌───┼───┐   ┌───┼───┐   ┌───┼───┐
    ▼   ▼   ▼   ▼   ▼   ▼   ▼   ▼   ▼
   A1  A2  A3  B1  B2  B3  C1  C2  C3
   
   评估每条路径，选择最优
```

**示例**: 解数学题

```
问题: 24 点游戏 (4, 7, 8, 8) → 24

探索路径:
Path A: (8 - 4) * (7 - 8) = 4 * (-1) = -4 ❌
Path B: (8 ÷ 8) * (7 * 4) = 1 * 28 = 28 ❌
Path C: (8 - 4 + 7) * 8 = 11 * 8 = 88 ❌
Path D: (8 - 7 + 4) * 8 = 5 * 8 = 40 ❌
Path E: 8 ÷ (4 - 8 ÷ 7) = ? (计算复杂) 暂停
Path F: (7 - 8 ÷ 8) * 4 = (7 - 1) * 4 = 24 ✅

选择 Path F
```

**适用场景**:
- ✅ 创意任务（需要探索多种方案）
- ✅ 决策优化（选择最优路径）
- ❌ Token 消耗大（探索多条路径）

---

## 🎯 如何选择范式

### 决策树

```
你的任务是...

├─ 单步简单任务
│  └─ 用普通 LLM 调用即可
│
├─ 需要工具调用的任务
│  ├─ 步骤固定、流程清晰
│  │  └─ 使用 Chain (链式)
│  │
│  ├─ 步骤不确定，需要动态决策
│  │  └─ 使用 ReAct ⭐ 最常用
│  │
│  └─ 复杂多步骤，需要整体优化
│     └─ 使用 Plan-and-Execute
│
├─ 需要高质量输出
│  └─ 使用 Reflexion (迭代改进)
│
└─ 需要探索多种方案
   └─ 使用 Tree of Thoughts
```

### 范式对比表

| 范式 | 优势 | 劣势 | Token 消耗 | 适用场景 |
|------|------|------|-----------|---------|
| **ReAct** | 灵活、可解释、通用 | 可能绕路 | 中等 | 🌟 **通用首选** |
| **Plan-and-Execute** | 步骤优化、高效 | 计划可能失效 | 较高 | 复杂流程任务 |
| **Reflexion** | 高质量输出 | 迭代成本高 | 很高 | 代码/文章生成 |
| **Tree of Thoughts** | 探索全面 | 消耗大、慢 | 极高 | 创意/决策任务 |
| **Chain** | 简单、快速 | 不灵活 | 低 | 固定流程 |

---

## 🛠️ 在你的 Agent Core 中应用

### 当前架构映射

你的 `agent_core` 已经具备了实现 ReAct 的基础：

```python
你的组件                    ReAct 对应部分
├── LLMClient          →   Thought 生成器
├── ToolCallHandler    →   Action 执行器
├── MCP Client         →   Observation 获取器
└── Orchestrator       →   整体循环控制器
```

### 推荐实现路线

#### Phase 1: 实现基础 ReAct (Zero-shot)

利用 OpenAI Function Calling：

```python
# core/orchestrator.py
async def process_query(self, request: AgentRequest) -> AgentResponse:
    messages = [{"role": "user", "content": request.user_query}]
    tools = await self.mcp_client.get_tools()
    
    max_iterations = 5
    for i in range(max_iterations):
        # Thought (隐式) + Action
        response = await self.llm_client.chat_completion(
            messages=messages,
            tools=tools
        )
        
        # 检查是否需要工具调用
        if not response.get("tool_calls"):
            # 没有更多 Action，任务完成
            return self._build_response(response)
        
        # Observation: 执行工具
        tool_results = await self.tool_handler.execute_tools(
            response["tool_calls"]
        )
        
        # 将 Observation 添加到 messages
        messages.append({
            "role": "assistant",
            "content": response.get("content"),
            "tool_calls": response["tool_calls"]
        })
        for result in tool_results:
            messages.append({
                "role": "tool",
                "tool_call_id": result["id"],
                "content": json.dumps(result["output"])
            })
    
    raise MaxIterationError("超过最大迭代次数")
```

#### Phase 2: 添加显式 Thought (可选)

如果你想看到 LLM 的思考过程：

```python
# 修改 system prompt
system_prompt = """
You are a helpful assistant. When solving tasks:
1. First, explain your thinking (Thought)
2. Then, call the appropriate tool (Action)
3. After getting results (Observation), continue thinking

Format your thoughts as:
Thought: [your reasoning]
[then call tools if needed]
"""

# 解析 LLM 返回的 Thought
if "Thought:" in response["content"]:
    thought = extract_thought(response["content"])
    log.info("LLM Thought", thought=thought, request_id=request.id)
```

#### Phase 3: 实现 Plan-and-Execute (进阶)

适合你的 `EventRouter` 模块：

```python
# core/event_router.py
async def plan_execution(self, query: str) -> ExecutionPlan:
    planning_prompt = f"""
    Create a step-by-step plan for: {query}
    
    Available tools: {self.tools}
    
    Return JSON:
    {{
        "steps": [
            {{"action": "tool_name", "reason": "why"}},
            ...
        ]
    }}
    """
    
    plan_response = await self.llm_client.chat_completion(
        messages=[{"role": "user", "content": planning_prompt}]
    )
    
    return ExecutionPlan.parse(plan_response)
```

---

## 📚 推荐阅读顺序

### 第 1 天: 理解基础
1. **ReAct 论文**: https://arxiv.org/abs/2210.03629
   - 重点读 Section 3 (Method) 和 Figure 2
   - 时间: 1 小时

2. **OpenAI Function Calling 文档**:
   - https://platform.openai.com/docs/guides/function-calling
   - 时间: 30 分钟

### 第 2 天: 看实现
3. **LangChain ReAct Agent 源码**:
   - https://github.com/langchain-ai/langchain/blob/master/libs/langchain/langchain/agents/react/agent.py
   - 重点看 `_get_action_and_input()` 方法
   - 时间: 1 小时

4. **动手实验**: 在你的 `agent_core` 中实现最简 ReAct 循环
   - 时间: 2-3 小时

### 第 3 天: 进阶范式
5. **Plan-and-Execute**:
   - LangChain 文档: https://python.langchain.com/docs/use_cases/more/agents/plan_and_execute
   - 时间: 1 小时

6. **Reflexion 论文**: https://arxiv.org/abs/2303.11366
   - 选读，了解自我反思机制
   - 时间: 1 小时

---

## 🎓 实战练习

### 练习 1: 手动模拟 ReAct
用纸笔模拟解决这个任务：
```
任务: "帮我查北京明天天气，如果会下雨就提醒我带伞"

可用工具:
- get_weather(city, date)
- send_reminder(message)

写出完整的 Thought-Action-Observation 过程
```

### 练习 2: 对比不同范式
同一个任务用 3 种范式实现：
```
任务: "帮我准备一份关于 AI 的演讲稿"

1. ReAct 版本
2. Plan-and-Execute 版本
3. Reflexion 版本

对比 token 消耗和质量
```

### 练习 3: 在 agent_core 中实现
```python
# 在你的项目中实现一个完整的 ReAct 循环
# 支持这个查询:
query = "查询北京明天天气，如果适合户外运动就推荐3个活动"

# 预期行为:
# Iteration 1: call get_weather("北京", "明天")
# Iteration 2: 基于天气结果，call search_activities("户外运动", "北京")
# Iteration 3: 返回最终答案
```

---

## 💡 关键要点总结

1. **ReAct 是最通用的范式**，适合 90% 的场景
2. **OpenAI Function Calling 是简化的 ReAct**，隐藏了 Thought
3. **你的 agent_core 已经具备实现 ReAct 的基础**
4. **从简单开始**: 先实现 Zero-shot ReAct，再考虑优化
5. **可观测性很重要**: 记录每次 Thought/Action/Observation，方便调试

---

## 🚀 下一步行动

- [ ] 阅读 ReAct 论文 Section 3
- [ ] 在 `orchestrator.py` 中实现基础 ReAct 循环
- [ ] 测试一个需要 2-3 轮工具调用的任务
- [ ] 添加日志记录每次迭代的过程
- [ ] 遇到问题随时回来讨论！

Good luck! 💪