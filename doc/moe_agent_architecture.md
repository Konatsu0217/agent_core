# MoE 风格的 Agent 路由架构设计

## 🎯 核心思想

```
                    User Query
                        │
                        ▼
              ┌──────────────────┐
              │  Fast Decider    │ ← 轻量级路由器（小模型/规则）
              │  (路由决策器)     │
              └─────────┬────────┘
                        │
           ┌────────────┴────────────┐
           ▼                         ▼
    ┌─────────────┐          ┌─────────────┐
    │ Fast Agent  │          │ Slow Agent  │
    │ (快速响应)   │          │ (深度推理)   │
    └─────────────┘          └─────────────┘
    • 单轮调用            • ReAct 循环
    • 小模型/缓存         • 多轮工具调用
    • < 500ms            • 3-10 秒
```

---

## 📐 完整架构设计

### 1. 整体结构

```asiic
agent_core/
├── core/
│   ├── orchestrator.py          # 主入口
│   ├── decider.py               # 🔥 NEW: 快速路由决策器
│   ├── fast_agent.py            # 🔥 NEW: 快速响应 Agent
│   ├── slow_agent.py            # 🔥 NEW: ReAct 深度推理 Agent
│   └── agent_interface.py       # 🔥 NEW: Agent 统一接口
│
├── clients/
│   ├── llm_client.py            # 支持多模型配置
│   └── ...
│
└── models/
    ├── agent_request.py
    ├── agent_response.py
    └── decider_result.py        # 🔥 NEW: 决策结果
```

---

## 🚀 核心模块设计

### Module 1: Agent Interface (统一接口)

```python
# core/agent_interface.py
from abc import ABC, abstractmethod
from models.agent_request import AgentRequest
from models.agent_response import AgentResponse

class BaseAgent(ABC):
    """所有 Agent 的统一接口"""
    
    @abstractmethod
    async def process(self, request: AgentRequest) -> AgentResponse:
        """处理用户请求"""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> dict:
        """返回 Agent 能力描述（用于 Decider 决策）"""
        pass
    
    @abstractmethod
    def estimate_cost(self, request: AgentRequest) -> dict:
        """估算处理该请求的成本（时间/Token）"""
        pass
```

---

### Module 2: Fast Agent (快速响应)

```python
# core/fast_agent.py
from core.agent_interface import BaseAgent

class FastAgent(BaseAgent):
    """
    快速响应 Agent
    - 使用小模型（如 GPT-3.5, Claude Haiku）
    - 单轮调用，不使用工具
    - 适合简单问答、闲聊、已知信息查询
    """
    
    def __init__(self, settings: AgentSettings):
        self.llm_client = LLMClient(
            model="gpt-3.5-turbo",  # 或 claude-3-haiku
            temperature=0.7
        )
        self.context_cache = {}  # 内置上下文缓存
    
    async def process(self, request: AgentRequest) -> AgentResponse:
        """单轮快速响应"""
        # 1. 检查缓存
        if cache_hit := self._check_cache(request.user_query):
            return cache_hit
        
        # 2. 构建简单 prompt
        messages = self._build_simple_messages(request)
        
        # 3. 单次 LLM 调用
        response = await self.llm_client.chat_completion(messages)
        
        # 4. 缓存结果
        self._cache_response(request.user_query, response)
        
        return AgentResponse(
            request_id=request.request_id,
            text_output=response["choices"][0]["message"]["content"],
            agent_type="fast",
            metadata={
                "latency_ms": 300,
                "tokens": 150,
                "cached": False
            }
        )
    
    def get_capabilities(self) -> dict:
        return {
            "type": "fast",
            "can_use_tools": False,
            "max_complexity": "simple",
            "avg_latency_ms": 300,
            "good_for": [
                "闲聊", "简单问答", "已知事实查询",
                "礼貌性回复", "情感回应"
            ]
        }
    
    def estimate_cost(self, request: AgentRequest) -> dict:
        return {
            "time_ms": 300,
            "tokens": 150,
            "price_usd": 0.0002
        }
    
    def _build_simple_messages(self, request: AgentRequest) -> list:
        """构建不带工具的简单消息"""
        return [
            {
                "role": "system",
                "content": self.context_cache.get("system_prompt", 
                    "你是一个友好的AI助手，提供简洁准确的回答。")
            },
            {
                "role": "user",
                "content": request.user_query
            }
        ]
```

---

### Module 3: Slow Agent (深度推理)

```python
# core/slow_agent.py
from core.agent_interface import BaseAgent
from handlers.tool_call_handler import ToolCallHandler

class SlowAgent(BaseAgent):
    """
    深度推理 Agent (ReAct)
    - 使用强模型（GPT-4, Claude Opus/Sonnet）
    - 多轮工具调用
    - 适合复杂任务、需要推理和规划的场景
    """
    
    def __init__(self, settings: AgentSettings):
        self.llm_client = LLMClient(
            model="gpt-4-turbo",  # 或 claude-3-5-sonnet
            temperature=0.7
        )
        self.tool_handler = ToolCallHandler(settings)
        self.pe_client = PEClient(settings)
        self.mcp_client = MCPClient(settings)
    
    async def process(self, request: AgentRequest) -> AgentResponse:
        """ReAct 多轮推理"""
        # 1. 调用 PE 构建完整请求（包含工具、RAG）
        llm_request = await self.pe_client.build_request(
            session_id=request.session_id,
            user_query=request.user_query
        )
        
        # 2. ReAct 循环
        messages = llm_request["messages"]
        tools = llm_request["tools"]
        
        max_iterations = 5
        iteration_logs = []
        
        for i in range(max_iterations):
            # Thought + Action
            response = await self.llm_client.chat_completion(
                messages=messages,
                tools=tools
            )
            
            iteration_logs.append({
                "iteration": i + 1,
                "thought": response.get("content"),
                "tool_calls": response.get("tool_calls")
            })
            
            # 检查是否需要工具调用
            if not response.get("tool_calls"):
                break
            
            # Observation: 执行工具
            tool_results = await self.tool_handler.execute_tools(
                response["tool_calls"]
            )
            
            # 更新 messages
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
        
        return AgentResponse(
            request_id=request.request_id,
            text_output=response["choices"][0]["message"]["content"],
            agent_type="slow",
            metadata={
                "iterations": i + 1,
                "total_tokens": sum([log["tokens"] for log in iteration_logs]),
                "latency_ms": 5000,
                "iteration_logs": iteration_logs
            }
        )
    
    def get_capabilities(self) -> dict:
        return {
            "type": "slow",
            "can_use_tools": True,
            "max_complexity": "high",
            "avg_latency_ms": 5000,
            "good_for": [
                "复杂推理", "多步骤任务", "需要工具调用",
                "数据分析", "代码生成", "深度问答"
            ]
        }
    
    def estimate_cost(self, request: AgentRequest) -> dict:
        return {
            "time_ms": 5000,
            "tokens": 2000,
            "price_usd": 0.02
        }
```

---

### Module 4: Fast Decider (快速路由器) ⚡

这是最关键的部分！需要**极快的决策速度**。

#### 方案 A: 规则 + 轻量级分类（推荐）

```python
# core/decider.py
import re
from typing import Literal

AgentType = Literal["fast", "slow"]

class FastDecider:
    """
    快速路由决策器
    - 优先使用规则匹配（0ms）
    - 规则无法判断时调用轻量级分类器（50-100ms）
    """
    
    def __init__(self, settings: AgentSettings):
        self.settings = settings
        # 使用最快的小模型做分类
        self.classifier_llm = LLMClient(
            model="gpt-3.5-turbo",  # 或者本地 LLaMA 3B
            temperature=0.0,  # 确定性输出
            max_tokens=10  # 只需要返回 "fast" 或 "slow"
        )
        
        # 规则模式
        self.fast_patterns = [
            r"^(你好|hi|hello|嗨)",  # 问候
            r"(谢谢|感谢)",           # 感谢
            r"^(什么是|define|解释一下)\s*[\w\u4e00-\u9fa5]{1,10}$",  # 简单定义
            r"^(今天|天气|日期|时间)",  # 常见查询
        ]
        
        self.slow_patterns = [
            r"(帮我|请|协助).*(分析|生成|创建|规划)",  # 复杂任务
            r"(搜索|查找|调查).*并.*",  # 多步骤
            r"(如果|假设|当).*那么.*",  # 条件推理
        ]
        
        # 关键词权重
        self.fast_keywords = {
            "你好": 10, "谢谢": 10, "什么是": 8, "天气": 7,
            "时间": 7, "日期": 7, "再见": 10
        }
        
        self.slow_keywords = {
            "分析": 8, "规划": 9, "比较": 7, "生成": 8,
            "搜索": 6, "调查": 7, "计算": 6, "推荐": 7
        }
    
    async def decide(self, request: AgentRequest) -> tuple[AgentType, dict]:
        """
        决策使用哪个 Agent
        返回: (agent_type, metadata)
        """
        query = request.user_query.strip()
        
        # Stage 1: 快速规则匹配 (0ms)
        if rule_result := self._rule_based_decision(query):
            return rule_result, {
                "method": "rule",
                "latency_ms": 0,
                "confidence": 0.95
            }
        
        # Stage 2: 关键词权重打分 (< 1ms)
        if score_result := self._keyword_scoring(query):
            return score_result, {
                "method": "keyword_scoring",
                "latency_ms": 1,
                "confidence": 0.85
            }
        
        # Stage 3: 轻量级 LLM 分类 (50-100ms)
        llm_result = await self._llm_classification(query)
        return llm_result, {
            "method": "llm_classification",
            "latency_ms": 80,
            "confidence": 0.90
        }
    
    def _rule_based_decision(self, query: str) -> AgentType | None:
        """基于正则规则的快速判断"""
        # 检查 Fast 模式
        for pattern in self.fast_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return "fast"
        
        # 检查 Slow 模式
        for pattern in self.slow_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return "slow"
        
        # 长度启发式
        if len(query) < 20 and "?" not in query:
            return "fast"
        
        return None
    
    def _keyword_scoring(self, query: str) -> AgentType | None:
        """关键词权重打分"""
        fast_score = sum(
            weight for keyword, weight in self.fast_keywords.items()
            if keyword in query
        )
        
        slow_score = sum(
            weight for keyword, weight in self.slow_keywords.items()
            if keyword in query
        )
        
        # 明确倾向时返回
        if fast_score > slow_score + 5:
            return "fast"
        elif slow_score > fast_score + 5:
            return "slow"
        
        return None
    
    async def _llm_classification(self, query: str) -> AgentType:
        """轻量级 LLM 分类（兜底方案）"""
        classification_prompt = f"""你是一个任务分类器。判断以下用户请求应该用快速响应还是深度推理：

快速响应 (fast)：简单问答、闲聊、已知事实查询
深度推理 (slow)：需要工具调用、多步骤推理、复杂分析

用户请求: {query}

只回复一个词: "fast" 或 "slow"
"""
        
        response = await self.classifier_llm.chat_completion(
            messages=[{"role": "user", "content": classification_prompt}],
            max_tokens=10,
            temperature=0.0
        )
        
        result = response["choices"][0]["message"]["content"].strip().lower()
        return "fast" if "fast" in result else "slow"
```

#### 方案 B: 本地小模型分类（更快但需要训练）

```python
class LocalDecider:
    """
    使用本地小模型（如 DistilBERT）做分类
    - 推理速度: 5-20ms
    - 需要预先训练或使用 Few-shot 提示
    """
    
    def __init__(self):
        from transformers import pipeline
        self.classifier = pipeline(
            "text-classification",
            model="distilbert-base-uncased-finetuned-sst-2-english",
            device=0  # GPU
        )
    
    async def decide(self, query: str) -> AgentType:
        # 本地推理，无网络延迟
        result = self.classifier(query)
        # 需要将 label 映射到 fast/slow
        return "fast" if result[0]["label"] == "SIMPLE" else "slow"
```

---

### Module 5: Orchestrator (主控制器)

```python
# core/orchestrator.py
from core.decider import FastDecider
from core.fast_agent import FastAgent
from core.slow_agent import SlowAgent

class AgentOrchestrator:
    """主调度器：MoE 风格路由"""
    
    def __init__(self, settings: AgentSettings):
        self.settings = settings
        
        # 初始化 Decider 和 Agents
        self.decider = FastDecider(settings)
        self.fast_agent = FastAgent(settings)
        self.slow_agent = SlowAgent(settings)
        
        # 统计信息
        self.stats = {
            "fast_count": 0,
            "slow_count": 0,
            "avg_fast_latency": 0,
            "avg_slow_latency": 0
        }
    
    async def process_query(self, request: AgentRequest) -> AgentResponse:
        """主入口：路由 + 执行"""
        start_time = time.time()
        
        # 1. 快速决策（< 100ms）
        agent_type, decision_meta = await self.decider.decide(request)
        
        logger.info(
            "Agent decision made",
            request_id=request.request_id,
            agent_type=agent_type,
            decision_method=decision_meta["method"],
            decision_latency_ms=decision_meta["latency_ms"]
        )
        
        # 2. 路由到对应 Agent
        if agent_type == "fast":
            response = await self.fast_agent.process(request)
            self.stats["fast_count"] += 1
        else:
            response = await self.slow_agent.process(request)
            self.stats["slow_count"] += 1
        
        # 3. 添加路由元信息
        response.metadata["routing"] = {
            "agent_type": agent_type,
            "decision_meta": decision_meta,
            "total_latency_ms": (time.time() - start_time) * 1000
        }
        
        return response
```

---

## 📊 性能对比

| 指标 | Fast Agent | Slow Agent |
|------|-----------|-----------|
| **模型** | GPT-3.5 / Claude Haiku | GPT-4 / Claude Sonnet |
| **延迟** | 200-500ms | 3-10 秒 |
| **Token 消耗** | 100-300 | 1000-5000 |
| **成本** | $0.0002 | $0.02 |
| **工具调用** | ❌ | ✅ |
| **适用场景** | 简单问答、闲聊 | 复杂推理、多步骤 |

---

## 🎯 Decider 决策逻辑可视化

```
User Query: "你好，今天天气怎么样？"
    │
    ▼
┌─────────────────────┐
│ Stage 1: 规则匹配    │
│ Pattern: ^(你好|hi) │ ✅ 匹配！
└──────────┬──────────┘
           │
           ▼
    返回: "fast" (0ms)


User Query: "帮我分析一下最近AI领域的发展趋势，并给出投资建议"
    │
    ▼
┌─────────────────────┐
│ Stage 1: 规则匹配    │ ❌ 无匹配
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Stage 2: 关键词打分  │
│ slow_score: 17      │ ✅ slow > fast + 5
│ (分析:8 + 投资:9)    │
└──────────┬──────────┘
           │
           ▼
    返回: "slow" (< 1ms)


User Query: "机器学习和深度学习有什么区别？"
    │
    ▼
┌─────────────────────┐
│ Stage 1: 规则匹配    │ ❌ 无匹配
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Stage 2: 关键词打分  │ ❌ 分数接近
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Stage 3: LLM 分类   │
│ Model: GPT-3.5-turbo│
│ Prompt: "判断任务..." │ ✅ 返回 "fast"
└──────────┬──────────┘
           │
           ▼
    返回: "fast" (80ms)
```

---

## 🚀 实现步骤

### Phase 1: 基础架构（1-2 天）
- [ ] 创建 `agent_interface.py`
- [ ] 实现 `FastAgent` 基础版本（单轮调用）
- [ ] 实现 `SlowAgent` 基础版本（复用现有 ReAct 逻辑）
- [ ] 更新 `Orchestrator` 支持路由

### Phase 2: 简单 Decider（0.5 天）
- [ ] 实现 `FastDecider._rule_based_decision()`
- [ ] 添加 10-20 条规则模式
- [ ] 测试规则覆盖率

### Phase 3: 增强 Decider（1 天）
- [ ] 实现 `_keyword_scoring()`
- [ ] 实现 `_llm_classification()` 作为兜底
- [ ] 添加决策日志和统计

### Phase 4: 优化（1-2 天）
- [ ] FastAgent 添加缓存机制
- [ ] 收集真实查询，优化规则
- [ ] A/B 测试不同决策策略

---

## 💡 优化建议

### 1. 缓存策略
```python
# FastAgent 中
class FastAgent:
    def __init__(self):
        self.cache = TTLCache(maxsize=1000, ttl=3600)  # 1小时过期
    
    def _check_cache(self, query: str) -> AgentResponse | None:
        # 相似度匹配（使用 embedding）
        query_embedding = self.embed(query)
        for cached_query, response in self.cache.items():
            if cosine_similarity(query_embedding, cached_query) > 0.95:
                return response
        return None
```

### 2. 动态阈值调整
```python
# Decider 根据历史表现动态调整
class AdaptiveDecider(FastDecider):
    def __init__(self):
        super().__init__()
        self.fast_success_rate = 0.85  # FastAgent 成功率
        self.slow_success_rate = 0.95
    
    def _adjust_threshold(self):
        # 如果 FastAgent 表现好，降低 slow 阈值
        if self.fast_success_rate > 0.90:
            self.slow_threshold += 1
```

### 3. 混合策略
```python
# 对于模糊情况，先用 Fast 试探
class HybridOrchestrator(AgentOrchestrator):
    async def process_query(self, request: AgentRequest):
        agent_type, confidence = await self.decider.decide(request)
        
        if agent_type == "fast" and confidence < 0.8:
            # 置信度低时，先快速尝试
            fast_response = await self.fast_agent.process(request)
            
            # 检查质量
            if self._is_response_good(fast_response):
                return fast_response
            else:
                # 降级到 Slow Agent
                return await self.slow_agent.process(request)
```

---

## 📈 监控指标

建议在 `Orchestrator` 中跟踪这些指标：

```python
class Metrics:
    # 路由分布
    fast_ratio: float  # Fast Agent 使用比例
    slow_ratio: float
    
    # 性能
    avg_decision_latency_ms: float  # 决策延迟
    avg_fast_latency_ms: float
    avg_slow_latency_ms: float
    
    # 质量
    fast_user_satisfaction: float  # 用户反馈
    slow_user_satisfaction: float
    fast_fallback_rate: float  # Fast 降级到 Slow 的比例
```

---

## 🎓 测试用例

```python
# tests/test_decider.py
test_cases = [
    # (query, expected_agent, max_latency_ms)
    ("你好", "fast", 5),
    ("谢谢你的帮助", "fast", 5),
    ("什么是机器学习？", "fast", 100),
    ("今天天气怎么样？", "fast", 100),
    
    ("帮我分析这份数据并生成报告", "slow", 100),
    ("搜索最近AI论文并总结要点", "slow", 100),
    ("如果明天下雨，帮我调整行程", "slow", 100),
]

@pytest.mark.asyncio
async def test_decider_accuracy():
    decider = FastDecider(settings)
    
    for query, expected, max_latency in test_cases:
        start = time.time()
        result, meta = await decider.decide(AgentRequest(query=query))
        latency = (time.time() - start) * 1000
        
        assert result == expected, f"Query '{query}' routed to {result}, expected {expected}"
        assert latency < max_latency, f"Decision took {latency}ms, expected < {max_latency}ms"
```

---

## ✅ 总结

你的 MoE 思路非常好！关键点：

1. **Decider 必须极快** (< 100ms)：优先用规则，兜底用轻量级 LLM
2. **FastAgent 处理 80% 的简单请求**：节省成本和时间
3. **SlowAgent 处理 20% 的复杂任务**：保证质量
4. **监控和迭代**：根据真实数据优化路由规则

这个架构在实际生产中非常实用，很多公司都在用类似方案！🚀

需要我帮你实现某个具体模块吗？比如 `FastDecider` 的完整代码？