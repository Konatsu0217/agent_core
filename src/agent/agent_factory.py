from typing import Dict, Any, Type, Optional
from src.agent.abs_agent import IBaseAgent, ExecutionMode
from src.agent.base_agents import BaseAgent, ToolUsingAgent, MemoryAwareAgent
from src.domain.models.agent_data_models import AgentRequest, AgentResponse
import asyncio
import json

class ServiceAwareAgent:
    """包含服务初始化逻辑的基类"""
    
    def _initialize_services(self, services_needed):
        """初始化服务"""
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
                    print(f"✅ 从容器获取 {service_name}")
                else:
                    print(f"⚠️ {service_name} 未注册")
        except ImportError:
            print("⚠️ 服务容器未初始化")

class AgentFactory:
    """Agent 工厂类，用于创建不同类型的 Agent 实例"""
    
    @staticmethod
    def create_agent(agent_profile: Dict[str, Any]) -> IBaseAgent:
        """
        根据 AgentProfile 创建不同类型的 Agent 实例
        
        Args:
            agent_profile: Agent 配置文件，包含以下字段：
                - name: Agent 名称
                - tools_use: 是否使用工具
                - memory: 是否使用记忆
                - services_needed: 需要的服务列表
                - 其他角色设定字段
                
        Returns:
            根据配置创建的 Agent 实例
        """
        # 从 AgentProfile 中提取配置
        name = agent_profile.get("name", "default_agent")
        use_tools = agent_profile.get("tools_use", False)
        use_memory = agent_profile.get("memory", False)
        work_flow_type = ExecutionMode(agent_profile.get("work_flow_type", "test"))
        output_format = agent_profile.get("output_format", "json")
        services_needed = agent_profile.get("services_needed", [])
        
        # 根据配置选择要创建的 Agent 类
        if use_tools and use_memory:
            # 同时使用工具和记忆
            return CombinedAgent(agent_profile, work_flow_type)
        elif use_tools:
            # 只使用工具
            return ToolOnlyAgent(agent_profile, work_flow_type)
        elif use_memory:
            # 只使用记忆
            return MemoryOnlyAgent(agent_profile, work_flow_type)
        else:
            # 基础 Agent
            return BasicAgent(agent_profile, work_flow_type)

class BasicAgent(BaseAgent, ServiceAwareAgent):
    """基础 Agent，不使用工具和记忆"""
    
    def __init__(self, agent_profile: Dict[str, Any], work_flow_type: ExecutionMode):
        name = agent_profile.get("name", "basic_agent")
        use_tools = agent_profile.get("tools_use", False)
        output_format = agent_profile.get("output_format", "json")
        super().__init__(name=name, work_flow_type=work_flow_type, use_tools=use_tools, output_format=output_format)
        
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
    
    async def process(self, request: AgentRequest) -> AgentResponse:
        """处理用户请求"""
        try:
            query = request.query
            
            # 构建消息
            messages = [{"role": "user", "content": query}]
            
            # 使用工具运行（虽然没有工具）
            from src.agent.abs_agent import run_llm_with_tools
            result = ""
            
            async for event in run_llm_with_tools(
                    self.backbone_llm_client,
                    messages,
                    []  # 空工具列表
            ):
                if event["event"] == "final_content":
                    result = event["content"]
                    break
            
            # 解析响应
            try:
                import json
                result_json = json.loads(result)
            except json.JSONDecodeError:
                result_json = {"response": result}
            
            return AgentResponse(
                pure_text=result,
                response=result_json,
                session_id=request.session_id
            )
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return AgentResponse(
                pure_text="",
                response={"error": str(e)},
                session_id=request.session_id
            )
    
    def get_capabilities(self) -> dict:
        """返回 Agent 能力描述"""
        return {
            "type": "basic",
            "description": "基础 Agent，不使用工具和记忆",
            "capabilities": []
        }

class ToolOnlyAgent(ToolUsingAgent, ServiceAwareAgent):
    """只使用工具的 Agent"""
    
    def __init__(self, agent_profile: Dict[str, Any], work_flow_type: ExecutionMode):
        name = agent_profile.get("name", "tool_only_agent")
        use_tools = agent_profile.get("tools_use", True)
        output_format = agent_profile.get("output_format", "json")
        super().__init__(name=name, work_flow_type=work_flow_type, use_tools=use_tools, output_format=output_format)
        
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
    
    async def process(self, request: AgentRequest) -> AgentResponse:
        """处理用户请求"""
        try:
            query = request.query
            
            # 获取工具列表
            tools = []
            if self.tool_manager:
                tools = await self.tool_manager.get_tools()
            
            # 构建消息
            messages = [{"role": "user", "content": query}]
            
            # 使用工具运行
            result = await self.run_with_tools(messages, tools)
            
            # 解析响应
            try:
                result_json = json.loads(result)
            except json.JSONDecodeError:
                result_json = {"response": result}
            
            return AgentResponse(
                pure_text=result,
                response=result_json,
                session_id=request.session_id
            )
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return AgentResponse(
                pure_text="",
                response={"error": str(e)},
                session_id=request.session_id
            )
    
    def get_capabilities(self) -> dict:
        """返回 Agent 能力描述"""
        return {
            "type": "tool_only",
            "description": "只使用工具的 Agent",
            "capabilities": ["tool_usage"]
        }

class MemoryOnlyAgent(MemoryAwareAgent, ServiceAwareAgent):
    """只使用记忆的 Agent"""
    
    def __init__(self, agent_profile: Dict[str, Any], work_flow_type: ExecutionMode):
        name = agent_profile.get("name", "memory_only_agent")
        use_tools = agent_profile.get("tools_use", False)
        output_format = agent_profile.get("output_format", "json")
        super().__init__(name=name, work_flow_type=work_flow_type, use_tools=use_tools, output_format=output_format)
        
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
    
    async def process(self, request: AgentRequest) -> AgentResponse:
        """处理用户请求"""
        try:
            query = request.query
            
            # 构建消息
            messages = [{"role": "user", "content": query}]
            
            # 使用工具运行（虽然没有工具）
            from src.agent.abs_agent import run_llm_with_tools
            result = ""
            
            async for event in run_llm_with_tools(
                    self.backbone_llm_client,
                    messages,
                    []  # 空工具列表
            ):
                if event["event"] == "final_content":
                    result = event["content"]
                    break
            
            # 解析响应
            try:
                import json
                result_json = json.loads(result)
            except json.JSONDecodeError:
                result_json = {"response": result}
            
            # 存储响应到缓存
            self.response_cache["query"] = query
            self.response_cache["response"] = result_json
            
            # 添加到记忆
            if request.extraInfo.get("add_memory", True) and self.memory_service:
                asyncio.create_task(self.add_memory(request.session_id))
            
            return AgentResponse(
                pure_text=result,
                response=result_json,
                session_id=request.session_id
            )
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return AgentResponse(
                pure_text="",
                response={"error": str(e)},
                session_id=request.session_id
            )
    
    def get_capabilities(self) -> dict:
        """返回 Agent 能力描述"""
        return {
            "type": "memory_only",
            "description": "只使用记忆的 Agent",
            "capabilities": ["memory"]
        }

class CombinedAgent(ToolUsingAgent, MemoryAwareAgent, ServiceAwareAgent):
    """同时使用工具和记忆的 Agent"""
    
    def __init__(self, agent_profile: Dict[str, Any], work_flow_type: ExecutionMode):
        name = agent_profile.get("name", "combined_agent")
        use_tools = agent_profile.get("tools_use", True)
        output_format = agent_profile.get("output_format", "json")
        
        # 初始化父类
        ToolUsingAgent.__init__(self, name=name, work_flow_type=work_flow_type, use_tools=use_tools, output_format=output_format)
        MemoryAwareAgent.__init__(self, name=name, work_flow_type=work_flow_type, use_tools=use_tools, output_format=output_format)
        
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
        
        if tool_manager and memory_service:
            try:
                from src.context.context_maker import DefaultContextMaker
                from src.context.augmenters.memory_augmenter import MemoryAugmenter
                from src.context.augmenters.tool_augmenter import ToolAugmenter
                
                context_maker = DefaultContextMaker()
                context_maker.add_augmenter(MemoryAugmenter(memory_service))
                context_maker.add_augmenter(ToolAugmenter(tool_manager))
                self.set_context_maker(context_maker)
                print("✅ 上下文构建器初始化完成")
            except ImportError:
                print("⚠️ 上下文构建器未初始化")
        else:
            print("⚠️ 上下文构建器初始化失败：缺少必要服务")
    
    async def process(self, request: AgentRequest) -> AgentResponse:
        """处理用户请求"""
        try:
            query = request.query
            
            # 获取工具列表
            tools = []
            if self.tool_manager:
                tools = await self.tool_manager.get_tools()
            
            # 构建消息
            messages = [{"role": "user", "content": query}]
            
            # 使用工具运行
            result = await self.run_with_tools(messages, tools)
            
            # 解析响应
            try:
                result_json = json.loads(result)
            except json.JSONDecodeError:
                result_json = {"response": result}
            
            # 存储响应到缓存
            self.response_cache["query"] = query
            self.response_cache["response"] = result_json
            
            # 添加到记忆
            if request.extraInfo.get("add_memory", True) and self.memory_service:
                asyncio.create_task(self.add_memory(request.session_id))
            
            return AgentResponse(
                pure_text=result,
                response=result_json,
                session_id=request.session_id
            )
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return AgentResponse(
                pure_text="",
                response={"error": str(e)},
                session_id=request.session_id
            )
    
    def get_capabilities(self) -> dict:
        """返回 Agent 能力描述"""
        return {
            "type": "combined",
            "description": "同时使用工具和记忆的 Agent",
            "capabilities": ["tool_usage", "memory"]
        }
