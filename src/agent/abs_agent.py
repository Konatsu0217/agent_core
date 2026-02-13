import asyncio
import json
import re
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from pyexpat.errors import messages
from typing import Any, Dict, Coroutine, Optional

from global_statics import logger
from src.context import context_maker
from src.context.augmenters import ScheduleAugmenter
from src.context.context import Context
from src.context.manager import get_context_manager
from src.domain.agent_data_models import AgentRequest
from src.infrastructure.clients.llm_clients.llm_client_manager import static_llmClientManager
from src.infrastructure.utils.pipe import ProcessPipe


async def _log_token_estimate(messages, model_name):
    await asyncio.to_thread(_log_token_estimate_sync, messages, model_name)


def _log_token_estimate_sync(messages, model_name):
    try:
        import tiktoken
        encoding = None
        if model_name:
            try:
                encoding = tiktoken.encoding_for_model(model_name)
            except Exception:
                encoding = None
        if encoding is None:
            encoding = tiktoken.get_encoding("cl100k_base")
    except Exception:
        logger.info("估算token: unknown")
        return
    try:
        payload = json.dumps(messages, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        payload = str(messages)
    tokens = len(encoding.encode(payload))
    logger.info(f"[LLM] 估算token: {tokens}")


async def run_llm_with_tools(llm_client, context: Context, pipe: ProcessPipe | None = None):
    buffer_delta = {"role": None, "content": []}
    tool_call_accumulator = {}

    current_type = None
    current_tool_name = None
    tool_call_id = None

    messages = [{"role": "system", "content": context.system_prompt}]
    memory_content = None
    if context.memory is not None:
        if isinstance(context.memory, dict):
            memory_content = context.memory.get("result")
        elif isinstance(context.memory, list):
            memory_content = "\n".join(str(item) for item in context.memory if item)
        else:
            memory_content = str(context.memory)
    if memory_content:
        messages.append({"role": "assistant", "content": memory_content})
    messages.extend(context.messages)

    if context.schedule:
        messages.append({"role": "system", "content": f"你需要参考日程表中的行动安排回答，忙碌时允许表示当前忙碌，当前日程表: {context.schedule}"})

    asyncio.create_task(_log_token_estimate(messages, getattr(llm_client, "model_name", None)))

    async for raw in llm_client.chat_completion_stream(
            messages=messages,
            tools=context.tools
    ):
        if pipe and pipe.is_closed():
            return
        data = json.loads(raw)
        delta = data["choices"][0]["delta"]
        finish_reason = data["choices"][0]["finish_reason"]

        # ==== Role ====
        if delta.get("role") and not buffer_delta["role"]:
            buffer_delta["role"] = delta["role"]

        # ==== Content ====
        if delta.get("content"):
            buffer_delta["content"].append(delta["content"])
            if pipe and not pipe.is_closed():
                await pipe.text_delta(delta["content"])

        # ==== Tool Calls ====
        if delta.get("tool_calls"):
            if pipe and pipe.is_closed():
                return
            for call in delta["tool_calls"]:
                cid = call["id"]
                if tool_call_id is None:
                    tool_call_id = cid
                if cid not in tool_call_accumulator:
                    if current_type is None:
                        current_type = call["type"]
                    if current_tool_name is None:
                        current_tool_name = call["function"]["name"]
                    tool_call_accumulator[cid] = {
                        "id": tool_call_id,
                        "type": call["type"],
                        "function": {
                            "name": call["function"]["name"],
                            "arguments": ""
                        }
                    }

                # 拼接 JSON 字符串片段
                if call["function"]["arguments"]:
                    tool_call_accumulator[cid]["function"]["arguments"] += call["function"]["arguments"]

                try:
                    args = tool_call_accumulator[cid]["function"]["arguments"]
                    parsed = json.loads(args)
                    # 如果成功解析 → yield 出去让外部执行
                    # messages.append(response.choices[0].message)
                    if pipe and pipe.is_closed():
                        return
                    yield {
                        "event": "tool_call",
                        "tool_call": {
                            "id": tool_call_id,
                            "type": current_type,
                            "function": {
                                "name": current_tool_name,
                                "arguments": parsed
                            }
                        }
                    }
                    # 这个调用已经发出去，不要再重复 yield
                    del tool_call_accumulator[cid]
                    current_tool_name = None
                    current_type = None
                    tool_call_id = None
                except:
                    pass  # JSON 还没拼完，继续流式等下一段

        # ==== 流结束 ====
        if finish_reason:
            if pipe and pipe.is_closed():
                return
            yield {
                "event": "final_content",
                "role": buffer_delta["role"],
                "content": "".join(buffer_delta["content"]),
            }
            return

class ExecutionMode(Enum):
    TEST = "test"
    ONE_SHOT = "one-shot"
    REACT = "ReAct"
    PLAN_AND_SOLVE = "Plan-and-Solve"


class IBaseAgent(ABC):
    """所有 Agent 的统一接口"""
    def __init__(self, agent_profile:Dict[str, Any], name: str, work_flow_type: ExecutionMode, use_tools: bool = True, output_format: str = "json"):
        # Agent 名称
        self.agent_id = agent_profile.get("agent_id", name)
        # 工作模式：one-shot / ReAct / Plan-and-Solve
        self.work_flow_type = work_flow_type
        # 是否启用工具
        self.use_tools = use_tools
        # 是否格式化输出，如果有格式化输出自己处理格式解析
        self.output_format = output_format
        # 全局的agent描述
        self.agent_profile = agent_profile

    @abstractmethod
    async def initialize(self):
        """初始化 Agent"""
        pass

    @abstractmethod
    async def process(self, request: AgentRequest, pipe: ProcessPipe) -> None:
        """处理用户请求，使用传入管道写出事件"""
        pass

    @abstractmethod
    def get_capabilities(self) -> dict:
        """返回 Agent 能力描述（用于 Decider 决策）"""
        pass

    @abstractmethod
    def estimate_cost(self, request: AgentRequest) -> dict:
        """估算处理该请求的成本（时间/Token）"""
        pass


class ServiceAwareAgent:
    """包含服务初始化逻辑的基类"""

    def __init__(self):
        """初始化服务感知Agent"""
        # 服务需求列表
        self.services_needed = []

    def _initialize_services(self, services_needed):
        """初始化服务"""
        # 保存服务需求
        self.services_needed = services_needed
        
        try:
            from src.di.container import get_service_container

            # 获取服务容器
            container = get_service_container()

            # 从容器中获取服务
            for service_name, setter_method in services_needed:
                service = container.get(service_name)
                if service:
                    if setter_method:
                        # 如果有setter方法，调用它设置服务
                        if hasattr(self, setter_method):
                            getattr(self, setter_method)(service)
                    else:
                        # 如果没有setter方法，直接设置为属性
                        setattr(self, service_name, service)
                    logger.info(f"✅ 从容器获取 {service_name}")
                else:
                    logger.warning(f"⚠️ {service_name} 未注册")
        except ImportError:
            logger.warning("⚠️ 服务容器未初始化")


class BaseAgent(IBaseAgent, ServiceAwareAgent):
    """基础 Agent 实现"""

    def __init__(self,agent_profile:Dict[str, Any], name: str, work_flow_type: ExecutionMode, use_tools: bool = True, output_format: str = "json"):
        # 初始化所有父类
        IBaseAgent.__init__(self,agent_profile=agent_profile, name=name, work_flow_type=work_flow_type, use_tools=use_tools, output_format=output_format)
        ServiceAwareAgent.__init__(self)
        
        # 从agent_profile中读取backbone_llm_config，如果没有则使用默认配置
        backbone_llm_config = agent_profile.get('backbone_llm_config')
        self.backbone_llm_client = static_llmClientManager.get_client(name=name, config=backbone_llm_config)

        self.context: Optional[Context] = None
        self.context_maker = None

    def set_context_maker(self, context_maker):
        """设置上下文构建器并注入服务"""
        # 注入服务
        context_maker.memory_service = getattr(self, "memory_service", None)
        context_maker.tool_manager = getattr(self, "tool_manager", None)
        context_maker.prompt_service = getattr(self, "prompt_service", None)
        context_maker.session_service = getattr(self, "session_service", None)
        # 设置上下文构建器
        self.context_maker = context_maker
        self.context_maker.agent_profile = self.agent_profile

    async def initialize(self):
        """初始化 Agent"""
        for argument in self.agent_profile.get("augmenters", []):
            if argument["name"] == "schedule_augmenter":
                request = AgentRequest(
                    session_id="init",
                    query=f"当前时间为{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}，请创建你今天的日程表，按30分钟为一个tick，只需要给出日程时间安排不需要任何额外描述"
                )
                await self.build_real_messages_and_tool(request)
                messages = [{"role": "system", "content": self.context.system_prompt},
                            {"role": "user", "content": request.query}]
                res = await self.backbone_llm_client.chat_completion(messages)
                self.context_maker.add_augmenter(ScheduleAugmenter(schedule=res["choices"][0]["message"]["content"]))
                self.context = None
        logger.info("[LLM] agent初始化完毕")


    async def process(self, request, pipe: ProcessPipe) -> None:
        """处理用户请求"""
        return None

    async def build_context(self, session_id: str, user_query: str, **kwargs):
        """使用ContextMaker构建上下文"""
        if self.context_maker:
            return await self.context_maker.build_context(session_id, user_query, **kwargs)
        else:
            # 如果没有ContextMaker，返回默认Context对象
            ctx = get_context_manager().create_context(
                session_id=session_id,
                agent_id=self.agent_profile["agent_id"],
                avatar_url=self.agent_profile.get("avatar_url"),
            )
            ctx.user_query = user_query
            return ctx

    async def build_real_messages_and_tool(self, request: AgentRequest):
        """构建真实的消息和工具"""
        query = request.query
        session_id = request.session_id
        self.context = await self.build_context(session_id, query, **request.extraInfo)


    def get_capabilities(self) -> dict:
        """返回 Agent 能力描述"""
        return {
            "type": "base",
            "description": "基础 Agent"
        }

    def estimate_cost(self, request) -> dict:
        """估算成本"""
        return {
            "time": 99999,
            "tokens": 99999
        }


class ToolUsingAgent(BaseAgent):
    """支持工具使用的 Agent"""

    def __init__(self, agent_profile:Dict[str, Any], name: str, work_flow_type: ExecutionMode, use_tools: bool = True, output_format: str = "json"):
        super().__init__(agent_profile=agent_profile, name=name, work_flow_type=work_flow_type, use_tools=use_tools, output_format=output_format)
        self.tool_manager = None

    def set_tool_manager(self, tool_manager):
        """设置工具管理器"""
        self.tool_manager = tool_manager

    async def run_with_tools(self, pipe: ProcessPipe | None = None) -> str:
        """使用工具运行"""
        MAX_STEPS = int(self.agent_profile.get("behavior").get("max_tool_calls"))  # 防死循环

        for _ in range(MAX_STEPS):
            tool_call_found = False
            final_answer = None

            async for event in run_llm_with_tools(
                    self.backbone_llm_client,
                    self.context,
                    pipe
            ):
                # ======== 工具调用 ========
                if event["event"] == "tool_call":
                    tool_call_found = True
                    call = event["tool_call"]
                    logger.info(f"[LLM] 工具调用: {call}")
                    if pipe and pipe.is_closed():
                        return None
                    if pipe:
                        await pipe.tool_call(name=call['function']['name'], arguments=call['function']['arguments'])

                    # 1. 执行工具
                    if pipe and pipe.is_closed():
                        return None
                    if self.tool_manager:
                        result = await self.tool_manager.call_tool(call)
                    else:
                        result = {"success": False, "error": "No tool manager set"}

                    # 2. 处理审批需求
                    if result.get("status") == "pending":
                        approval_id = result.get("approval_id")
                        approval_data = result.get("data", {})

                        if pipe:
                            await pipe.approval_required(
                                name=call['function']['name'],
                                arguments=call['function']['arguments'],
                                approval_id=approval_id,
                                message=approval_data.get('message', ''),
                                safety_assessment=approval_data.get('safety_assessment', {})
                            )
                        
                        # 审批决定由 pipe 提供
                        if pipe:
                            decision = await pipe.wait_for_approval(approval_id)
                            if decision == "approved":
                                approval_result = await self.tool_manager.approve_tool(approval_id)
                                logger.info(f"[MCP] 批准结果: {approval_result}")
                                result = approval_result
                            else:
                                rejection_result = await self.tool_manager.reject_tool(approval_id)
                                logger.warning(f"[MCP] 拒绝结果: {rejection_result}")
                                result = rejection_result
                        else:
                            rejection_result = await self.tool_manager.reject_tool(approval_id)
                            logger.warning(f"[MCP] 拒绝结果: {rejection_result}")
                            result = rejection_result

                    # 3. 将工具结果加入 messages
                    if result.get("success") is False:
                        error_msg = result.get("error", "") or result.get("message", "")
                        if pipe:
                            await pipe.tool_result(call['function']['name'], False, {"error": error_msg})
                        if pipe and pipe.is_closed():
                            return None
                        self.context.messages.append({
                            "role": "user",
                            "content": f"工具调用 {call['id']} 失败：{error_msg}"
                        })
                        continue

                    msg = result.get("result", {}).get("data", "") or result.get("result", "")
                    if pipe:
                        await pipe.tool_result(call['function']['name'], True, msg)
                    if pipe and pipe.is_closed():
                        return None
                    await self.append_tool_call(self.context.messages, call, msg, final_answer)

                    # 注意：不要 break —— event 的流要读完
                    continue

                # ======== 最终输出 ========
                elif event["event"] == "final_content":
                    final_answer = event["content"]
                    # 继续读流，但最终要退出大循环
                    continue

            # ========= 一轮流结束后 =========
            if tool_call_found:
                # 有工具调用 → 开启下一轮 LLM 运行
                logger.info("[LLM] 检测到工具调用，进入下一轮")
                continue

            # 没有工具调用 → 直接返回最终答案
            logger.info("[LLM] 无工具调用，返回最终结果")
            if pipe and pipe.is_closed():
                return None
            if pipe:
                await pipe.final_text(final_answer or "")
                # 过滤各种标签 [xxx] 和 {xxx}
                final_answer = re.sub(r'\[.*?\]', '', final_answer)
                final_answer = re.sub(r'\{.*?\}', '', final_answer)
                self.context.messages.append({"role": "assistant", "content": final_answer})
            return final_answer

        # 超出最大循环
        await  pipe.final_text("Exceeded max ReAct steps!!" or "")
        logger.warning("[LLM] 工具调用轮次达到上限")
        return "{\"error\": \"Exceeded max ReAct steps\"}"

    @staticmethod
    async def append_tool_call(messages, call, msg, final_answer = ""):
        """添加工具调用结果到消息列表"""
        messages.append({
            "role": "assistant",
            "content": final_answer,
            "tool_calls": [
                {
                    "id": call["id"],
                    "type": "function",
                    "function": {
                        "name": call["function"]["name"],
                        "arguments": json.dumps(call["function"]["arguments"])
                    }
                }
            ]
        })
        messages.append({
            "role": "tool",
            "tool_call_id": call["id"],
            "content": str(msg),
        })


class MemoryAwareAgent(BaseAgent):
    """支持记忆管理的 Agent"""

    def __init__(self,agent_profile:Dict[str, Any], name: str, work_flow_type: ExecutionMode, use_tools: bool = True, output_format: str = "json"):
        super().__init__(agent_profile= agent_profile, name=name, work_flow_type=work_flow_type, use_tools=use_tools, output_format=output_format)
        self.memory_service = None
        self.response_cache: Dict[str, str] = {}

    def set_memory_service(self, memory_service):
        """设置记忆服务"""
        self.memory_service = memory_service

    async def memory_hook(self, request: AgentRequest, text: str) -> Coroutine[Any, Any, None] | None:
        if request.extraInfo.get("add_memory", True) and self.memory_service:
            self.response_cache["query"] = request.query
            self.response_cache["response"] = {"response": text}
            await self.add_memory(request.session_id)
            return None
        return None

    async def add_memory(self, session_id: str) -> None:
        """添加记忆"""
        if not self.memory_service:
            return

        messages = [{
            "role": "user",
            "content": self.response_cache.get("query", "")
        }, {
            "role": "assistant",
            "content": self.response_cache.get("response", "")
        }]
        self.response_cache.clear()
        await self.memory_service.add(messages, session_id)
