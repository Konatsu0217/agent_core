import asyncio
import json

# 尝试导入 json_repair，如果失败则使用普通 json
try:
    import json_repair
    has_json_repair = True
except ImportError:
    has_json_repair = False
    print("⚠️ json_repair 模块未安装，将使用普通 json 解析")

from src.agent.abs_agent import ExecutionMode
from src.agent.base_agents import ToolUsingAgent, MemoryAwareAgent
from src.domain.models.agent_data_models import AgentRequest, AgentResponse


class FastAgent(ToolUsingAgent, MemoryAwareAgent):
    """快速响应 Agent"""
    
    def __init__(self,
                 work_flow_type: ExecutionMode = ExecutionMode.TEST,
                 name: str = "fast_agent",
                 use_tools: bool = True,
                 output_format: str = "json"):
        # 初始化父类
        ToolUsingAgent.__init__(self, name=name, work_flow_type=work_flow_type, use_tools=use_tools, output_format=output_format)
        MemoryAwareAgent.__init__(self, name=name, work_flow_type=work_flow_type, use_tools=use_tools, output_format=output_format)

        # 声明需要的服务列表 [(服务名称, 设置方法名)]
        self.services_needed = [
            ("tool_manager", "set_tool_manager"),
            ("memory_service", "set_memory_service"),
            ("prompt_service", None),
            ("session_service", None),
            ("query_wrapper", None)
        ]
        
        # 服务实例
        self.prompt_service = None
        self.session_service = None
        self.query_wrapper = None
        
        # 初始化服务
        self._initialize_services()

    def _initialize_services(self):
        """初始化服务"""
        from src.di.container import get_service_container

        # 获取服务容器
        container = get_service_container()

        # 从容器中获取服务
        for service_name, setter_method in self.services_needed:
            service = container.get(service_name)
            if service:
                if setter_method:
                    # 如果有setter方法，调用它设置服务
                    getattr(self, setter_method)(service)
                else:
                    # 如果没有setter方法，直接设置为属性
                    setattr(self, service_name, service)
                print(f"✅ 从容器获取 {service_name}")
            else:
                print(f"⚠️ {service_name} 未注册")

        # 上下文构建器（如果有必要的服务）
        tool_manager = getattr(self, "tool_manager", None)
        memory_service = getattr(self, "memory_service", None)

        if tool_manager and memory_service:
            from src.context.context_maker import DefaultContextMaker
            from src.context.augmenters.memory_augmenter import MemoryAugmenter
            from src.context.augmenters.tool_augmenter import ToolAugmenter

            context_maker = DefaultContextMaker()
            context_maker.add_augmenter(MemoryAugmenter(memory_service))
            context_maker.add_augmenter(ToolAugmenter(tool_manager))
            self.set_context_maker(context_maker)
            print("✅ 上下文构建器初始化完成")
        else:
            print("⚠️ 上下文构建器初始化失败：缺少必要服务")

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

    async def process(self, request: AgentRequest) -> AgentResponse:
        """处理用户请求"""
        try:
            query = request.query
            if self.query_wrapper:
                query = self.query_wrapper.wrap_query(request.query)

            # 并行获取所有需要的信息
            messages, tools = await self._get_prompt_and_tools(
                session_id=request.session_id,
                user_query=query
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

            if self.query_wrapper:
                self.response_cache = self.query_wrapper.parse_response(request, result_json)
            else :
                self.response_cache["query"] = request.query
                self.response_cache["response"] = result_json

            if request.extraInfo.get("add_memory", True):
                asyncio.create_task(self.add_memory(request.session_id))

        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return AgentResponse(
                pure_text="",
                response={"error": str(e)},
                session_id=request.session_id
            )

        if result_json is dict:
            return AgentResponse(
                pure_text=result,
                response=result_json,
                session_id=request.session_id
            )

        return AgentResponse(
            pure_text=result,
            response=dict(),
            session_id=request.session_id
        )

    async def _get_prompt_and_tools(self, session_id: str, user_query: str):
        """获取提示词和工具"""
        # 统一创建 Task 对象
        tasks = []

        # 构建提示词
        if self.prompt_service:
            pe_task = asyncio.create_task(self.prompt_service.build_prompt(
                session_id=session_id,
                user_query=user_query
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
