import asyncio
from typing import Any, Dict, Coroutine

from src.agent.abs_agent import ExecutionMode, BaseAgent, ToolUsingAgent, \
    MemoryAwareAgent, assemble_messages
from src.domain.models import AgentRequest
from src.infrastructure.utils.pipe import ProcessPipe


class BasicAgent(BaseAgent):
    """基础 Agent，不使用工具和记忆"""

    def __init__(self, agent_profile: Dict[str, Any], work_flow_type: ExecutionMode):
        name = agent_profile.get("name", "basic_agent")
        use_tools = agent_profile.get("tools_use", False)
        output_format = agent_profile.get("output_format", "json")
        super().__init__(agent_profile=agent_profile, name=name, work_flow_type=work_flow_type, use_tools=use_tools, output_format=output_format)

        # 角色设定提示词字段（占位）
        self.role_profile = {
            "role": agent_profile.get("role", ""),
            "description": agent_profile.get("description", ""),
            "capabilities": agent_profile.get("capabilities", []),
            "tone": agent_profile.get("tone", ""),
            "constraints": agent_profile.get("constraints", []),
            "tools": agent_profile.get("tools", []),
            "routing_rules": agent_profile.get("routing_rules", {}),
            "agent_id": agent_profile.get("agent_id", "")
        }

        # 初始化服务
        self._initialize_services(agent_profile.get("services_needed", []))

    async def initialize(self):
        """初始化 Agent"""
        pass

    async def process(self, request: AgentRequest, pipe: ProcessPipe) -> None:
        try:
            messages, tools = await self.build_real_messages_and_tool(request)

            from src.agent.abs_agent import run_llm_with_tools

            async def _run():
                async for event in run_llm_with_tools(
                        self.backbone_llm_client,
                        messages,
                        tools,
                        pipe
                ):
                    if event["event"] == "final_content":
                        await pipe.final_text(event["content"])

            asyncio.create_task(_run())
        except Exception as e:
            await pipe.error(str(e))

    async def history_hook(self, request: AgentRequest, messages: list[dict[str, str]]) -> Coroutine[Any, Any, None] | None:
        pass

    def get_capabilities(self) -> dict:
        """返回 Agent 能力描述"""
        return {
            "type": "basic",
            "description": "基础 Agent，不使用工具和记忆",
            "capabilities": []
        }


class ToolOnlyAgent(ToolUsingAgent):
    """只使用工具的 Agent"""

    def __init__(self, agent_profile: Dict[str, Any], work_flow_type: ExecutionMode):
        name = agent_profile.get("name", "tool_only_agent")
        use_tools = agent_profile.get("tools_use", True)
        output_format = agent_profile.get("output_format", "json")
        super().__init__(agent_profile=agent_profile, name=name, work_flow_type=work_flow_type, use_tools=use_tools, output_format=output_format)

        # 角色设定提示词字段（占位）
        self.role_profile = {
            "role": agent_profile.get("role", ""),
            "description": agent_profile.get("description", ""),
            "capabilities": agent_profile.get("capabilities", []),
            "tone": agent_profile.get("tone", ""),
            "constraints": agent_profile.get("constraints", []),
            "tools": agent_profile.get("tools", []),
            "routing_rules": agent_profile.get("routing_rules", {}),
            "agent_id": agent_profile.get("agent_id", "")
        }

        # 初始化服务
        self._initialize_services(agent_profile.get("services_needed", []))

    async def process(self, request: AgentRequest, pipe: ProcessPipe) -> None:
        try:
            messages, tools = await self.build_real_messages_and_tool(request)

            async def _run():
                await self.run_with_tools(messages, tools, pipe)

            asyncio.create_task(_run())
        except Exception as e:
            await pipe.error(str(e))

    def get_capabilities(self) -> dict:
        """返回 Agent 能力描述"""
        return {
            "type": "tool_only",
            "description": "只使用工具的 Agent",
            "capabilities": ["tool_usage"]
        }


class MemoryOnlyAgent(MemoryAwareAgent):
    """只使用记忆的 Agent"""

    def __init__(self, agent_profile: Dict[str, Any], work_flow_type: ExecutionMode):
        name = agent_profile.get("name", "memory_only_agent")
        use_tools = agent_profile.get("tools_use", False)
        output_format = agent_profile.get("output_format", "json")
        super().__init__(agent_profile=agent_profile, name=name, work_flow_type=work_flow_type, use_tools=use_tools, output_format=output_format)

        # 角色设定提示词字段（占位）
        self.role_profile = {
            "role": agent_profile.get("role", ""),
            "description": agent_profile.get("description", ""),
            "capabilities": agent_profile.get("capabilities", []),
            "tone": agent_profile.get("tone", ""),
            "constraints": agent_profile.get("constraints", []),
            "tools": agent_profile.get("tools", []),
            "routing_rules": agent_profile.get("routing_rules", {}),
            "agent_id": agent_profile.get("agent_id", "")
        }

        # 初始化服务
        self._initialize_services(agent_profile.get("services_needed", []))

    async def process(self, request: AgentRequest, pipe: ProcessPipe) -> None:
        try:
            messages, tools = await self.build_real_messages_and_tool(request)

            from src.agent.abs_agent import run_llm_with_tools

            async def _run():
                async for event in run_llm_with_tools(
                        self.backbone_llm_client,
                        messages,
                        tools,
                        pipe
                ):
                    if event["event"] == "final_content":
                        await pipe.final_text(event["content"])
                text = await pipe.final
                asyncio.create_task(self.memory_hook(request, text))

            asyncio.create_task(_run())
        except Exception as e:
            await pipe.error(str(e))

    def get_capabilities(self) -> dict:
        """返回 Agent 能力描述"""
        return {
            "type": "memory_only",
            "description": "只使用记忆的 Agent",
            "capabilities": ["memory"]
        }


class CombinedAgent(ToolUsingAgent, MemoryAwareAgent):
    """同时使用工具和记忆的 Agent"""

    def __init__(self, agent_profile: Dict[str, Any], work_flow_type: ExecutionMode):
        name = agent_profile.get("name", "combined_agent")
        use_tools = agent_profile.get("tools_use", True)
        output_format = agent_profile.get("output_format", "json")

        # 初始化父类
        ToolUsingAgent.__init__(self, agent_profile=agent_profile, name=name, work_flow_type=work_flow_type, use_tools=use_tools,
                                output_format=output_format)
        MemoryAwareAgent.__init__(self, agent_profile=agent_profile, name=name, work_flow_type=work_flow_type, use_tools=use_tools,
                                  output_format=output_format)

        # 角色设定提示词字段（占位）
        self.role_profile = {
            "role": agent_profile.get("role", ""),
            "description": agent_profile.get("description", ""),
            "capabilities": agent_profile.get("capabilities", []),
            "tone": agent_profile.get("tone", ""),
            "constraints": agent_profile.get("constraints", []),
            "tools": agent_profile.get("tools", []),
            "routing_rules": agent_profile.get("routing_rules", {}),
            "agent_id": agent_profile.get("agent_id", "")
        }

        # 初始化服务
        self._initialize_services(agent_profile.get("services_needed", []))
        # 初始化上下文构建器
        self._initialize_context_maker()

    def _initialize_context_maker(self):
        """初始化上下文构建器"""
        # 上下文构建器（如果有必要的服务）
        tool_manager = getattr(self, "tool_manager", None)
        memory_service = getattr(self, "memory_service", None)
        prompt_service = getattr(self, "prompt_service", None)

        try:
            from src.context.context_maker import DefaultContextMaker

            # 创建ContextMaker实例并传入服务
            context_maker = DefaultContextMaker(
                memory_service=memory_service,
                tool_manager=tool_manager,
                prompt_service=prompt_service
            )
            
            self.set_context_maker(context_maker)
            print("✅ 上下文构建器初始化完成")
        except ImportError:
            print("⚠️ 上下文构建器未初始化")

    async def process(self, request: AgentRequest, pipe: ProcessPipe) -> None:
        try:
            messages, tools = await self.build_real_messages_and_tool(request)

            async def _run():
                await self.run_with_tools(messages, tools, pipe)
                text = await pipe.final
                asyncio.create_task(self.memory_hook(request, text))

            asyncio.create_task(_run())
        except Exception as e:
            await pipe.error(str(e))

    def get_capabilities(self) -> dict:
        """返回 Agent 能力描述"""
        return {
            "type": "combined",
            "description": "同时使用工具和记忆的 Agent",
            "capabilities": ["tool_usage", "memory"]
        }
