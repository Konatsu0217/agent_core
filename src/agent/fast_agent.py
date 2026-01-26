import asyncio
import json
import logging
from typing import Any, Optional

# 尝试导入 json_repair，如果失败则使用普通 json
try:
    import json_repair
    has_json_repair = True
except ImportError:
    has_json_repair = False
    print("⚠️ json_repair 模块未安装，将使用普通 json 解析")

from src.agent.abs_agent import ExecutionMode
from src.agent.base_agents import ToolUsingAgent, MemoryAwareAgent
from src.services.impl.mcp_tool_manager import McpToolManager
from src.services.impl.pe_prompt_service import PePromptService
from src.services.impl.mem0_memory_service import Mem0MemoryService
from src.services.impl.default_session_service import DefaultSessionService
from src.context.context_maker import DefaultContextMaker
from src.context.augmenters.memory_augmenter import MemoryAugmenter
from src.context.augmenters.tool_augmenter import ToolAugmenter
from src.domain.models.agent_data_models import AgentRequest, AgentResponse


class FastAgent(ToolUsingAgent, MemoryAwareAgent):
    """快速响应 Agent"""
    
    def __init__(self, extra_prompt: Optional[str] = None,
                 work_flow_type: ExecutionMode = ExecutionMode.TEST,
                 name: str = "fast_agent",
                 use_tools: bool = True,
                 output_format: str = "json"):
        # 初始化父类
        ToolUsingAgent.__init__(self, name=name, work_flow_type=work_flow_type, use_tools=use_tools, output_format=output_format)
        MemoryAwareAgent.__init__(self, name=name, work_flow_type=work_flow_type, use_tools=use_tools, output_format=output_format)
        
        self.extra_prompt: Optional[str] = extra_prompt
        
        # 服务实例
        self.prompt_service = None
        self.session_service = None
        
        # 初始化服务
        self._initialize_services()

    def _initialize_services(self):
        """初始化服务"""
        # 工具管理器
        tool_manager = McpToolManager()
        self.set_tool_manager(tool_manager)
        
        # 记忆服务
        memory_service = Mem0MemoryService()
        self.set_memory_service(memory_service)
        
        # 其他服务
        self.prompt_service = PePromptService()
        self.session_service = DefaultSessionService()
        
        # 上下文构建器
        context_maker = DefaultContextMaker()
        context_maker.add_augmenter(MemoryAugmenter(memory_service))
        context_maker.add_augmenter(ToolAugmenter(tool_manager))
        self.set_context_maker(context_maker)

    async def initialize(self):
        """初始化 Agent"""
        # 初始化所有服务
        tasks = []
        
        if self.tool_manager:
            tasks.append(self.tool_manager.initialize())
        
        if self.prompt_service:
            tasks.append(self.prompt_service.initialize())
        
        if tasks:
            await asyncio.gather(*tasks)

    def warp_query(self, query: str) -> str:
        """包装用户查询，添加必要的上下文"""
        return f"用户查询: {query}, system: 你的回复必须为json格式{{\"response\": \"你的回复\",\"action\": \"简短、精准地表述你要做的肢体动作，使用英文\",\"expression\": \"从我为你提供的tool_type = resource中选择表情(可选，如果未提供则为空字符串)\"}} \n/no_think"

    async def process(self, request: AgentRequest) -> AgentResponse:
        """处理用户请求"""
        try:
            if self.extra_prompt is None:
                self.extra_prompt = ""

            # 并行获取所有需要的信息
            messages, tools = await self._get_prompt_and_tools(
                session_id=request.session_id,
                user_query=self.warp_query(request.query),
                extra_prompt=self.extra_prompt,
            )

            if self.use_tools:
                result = await self.run_with_tools(messages, tools)
            else:
                result = await self.run_with_tools(messages, [])

            if has_json_repair:
                result_json = json_repair.loads(result)
            else:
                # 使用普通 json 解析，添加错误处理
                try:
                    result_json = json.loads(result)
                except json.JSONDecodeError:
                    # 如果解析失败，返回错误响应
                    result_json = {"response": "解析响应失败", "action": "", "expression": ""}
            # 用来存聊天记录
            self.response_cache["query"] = request.query
            self.response_cache["response"] = result_json.get("response", "")
            self.response_cache["action"] = result_json.get("action", "")
            self.response_cache["expression"] = result_json.get("expression", "")

            if request.extraInfo.get("add_memory", True):
                asyncio.create_task(self.add_memory(request.session_id))

        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return AgentResponse(
                response={"error": str(e)},
                session_id=request.session_id
            )

        return AgentResponse(
            response=result_json,
            session_id=request.session_id
        )

    async def _get_prompt_and_tools(self, session_id: str, user_query: str, extra_prompt: str = ""):
        """获取提示词和工具"""
        # 统一创建 Task 对象
        tasks = []

        # 构建提示词
        if self.prompt_service:
            pe_task = asyncio.create_task(self.prompt_service.build_prompt(
                session_id=session_id,
                user_query=user_query,
                system_resources=extra_prompt
            ))
            tasks.append(pe_task)
        else:
            async def empty_pe_task():
                return {"llm_request": {"messages": [{"role": "user", "content": user_query}]}}
            tasks.append(empty_pe_task())

        # 搜索记忆
        if self.memory_service:
            rag_task = asyncio.create_task(self.memory_service.search(
                query=user_query, 
                user_id=session_id, 
                limit=5
            ))
            tasks.append(rag_task)
        else:
            async def empty_rag_task():
                return []
            tasks.append(empty_rag_task())

        # 获取工具
        if self.tool_manager:
            tools_task = asyncio.create_task(self.tool_manager.get_tools())
            tasks.append(tools_task)
        else:
            async def empty_tools_task():
                return []
            tasks.append(empty_tools_task())

        # 获取会话
        if self.session_service:
            session_task = asyncio.create_task(self.session_service.get_session(
                session_id, "DefaultAgent"
            ))
            tasks.append(session_task)
        else:
            async def empty_session_task():
                return None
            tasks.append(empty_session_task())

        # 并行执行
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=5
            )

            llm_request_response, rag_results, tools, session_history = results

            # 处理异常
            if isinstance(llm_request_response, Exception):
                print(f"❌ PE build_prompt failed: {llm_request_response}")
                return [], []

            if isinstance(tools, Exception):
                print(f"⚠️ ToolManager get_tools failed: {tools}")
                tools = []

            if isinstance(rag_results, Exception):
                print(f"⚠️ MemoryService search failed: {rag_results}")
                rag_results = []

            # 正确提取数据
            llm_request = llm_request_response.get("llm_request", {})
            messages = llm_request.get("messages", [])

            if session_history:
                session_messages = session_history.get("messages", [])
                messages = messages[:-1] + session_messages + messages[-1:]

            if rag_results:
                if messages:
                    messages[0]["content"] += f"\n\n[Relevant Memory]: {rag_results} \n\n"

            return messages, tools

        except asyncio.TimeoutError:
            print("❌ Timeout: Service request took too long")
            return [], []
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return [], []

    def get_capabilities(self) -> dict:
        """返回 Agent 能力描述"""
        return {
            "type": "fast",
            "description": "快速响应 Agent",
            "capabilities": ["tool_usage", "memory", "prompt_engineering"]
        }

    def estimate_cost(self, request: AgentRequest) -> dict:
        """估算成本"""
        return {
            "time": 99999,  # 100ms
            "tokens": 99999  # 假设每个请求 10 个 Token
        }
