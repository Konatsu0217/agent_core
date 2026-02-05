from typing import Dict, Optional, Any

from src.agent import BaseAgent
from src.domain.agent_data_models import AgentRequest
from src.infrastructure.utils.pipe import ProcessPipe


async def run_with_pipe(agent:BaseAgent, request: AgentRequest, pipe: ProcessPipe) -> None:
    """使用管道处理请求"""
    await agent.process(request, pipe)


class AgentCoordinator:
    """Agent 协调器"""
    
    def __init__(self):
        self.agents: Dict[str, Any] = {}
        self.task_dispatcher: Optional[TaskDispatcher] = None
        # 初始化服务容器
        from src.di.container import get_service_container
        from src.di.services.impl.default_query_wrapper_service import DefaultQueryWrapper
        from src.di.services.impl.mcp_tool_manager import McpToolManager
        from src.di.services.impl.pe_prompt_service import PePromptService
        from src.di.services.impl.default_session_service import DefaultSessionService

        # 获取服务容器
        container = get_service_container()
        # 注册服务
        container.register("query_wrapper", DefaultQueryWrapper())
        container.register("tool_manager", McpToolManager())
        # container.register("memory_service", Mem0MemoryService())
        container.register("prompt_service", PePromptService())
        container.register("session_service", DefaultSessionService())
        print("✅ 所有服务注册完成")
    
    def register_agent(self, agent):
        """注册 Agent"""
        self.agents[agent.name] = agent
    
    def get_agent(self, agent_name: str) -> Optional[Any]:
        """获取 Agent"""
        return self.agents.get(agent_name)
    
    def set_task_dispatcher(self, task_dispatcher):
        """设置任务分发器"""
        self.task_dispatcher = task_dispatcher
    
    async def process_request(self, request: AgentRequest,  pipe: ProcessPipe, agent_name: Optional[str] = None) -> None:
        """处理请求"""
        # 如果指定了 Agent，直接使用
        if agent_name:
            agent = self.get_agent(agent_name)
            await run_with_pipe(agent, request, pipe)
            return
        
        # 否则使用任务分发器选择 Agent
        if self.task_dispatcher:
            selected_agent = await self.task_dispatcher.select_agent(request, self.agents)
            if selected_agent:
                await run_with_pipe(selected_agent, request, pipe)
                return
        
        # 默认使用第一个 Agent
        if self.agents:
            default_agent = next(iter(self.agents.values()))
            await run_with_pipe(default_agent, request, pipe)
            return

        return

    async def initialize_all_agents(self):
        """初始化所有 Agent"""
        tasks = []
        for agent in self.agents.values():
            if hasattr(agent, "initialize"):
                tasks.append(agent.initialize())
        if tasks:
            await asyncio.gather(*tasks)


class TaskDispatcher:
    """任务分发器"""
    
    async def select_agent(self, request: AgentRequest, agents: Dict[str, Any]) -> Optional[Any]:
        """选择合适的 Agent"""
        # 简单的基于请求类型的选择策略
        query = request.query.lower()
        
        # 根据查询内容选择 Agent
        for agent_name, agent in agents.items():
            capabilities = agent.get_capabilities()
            if self._match_request(query, capabilities):
                return agent
        
        # 返回第一个可用的 Agent
        if agents:
            return next(iter(agents.values()))
        
        return None
    
    def _match_request(self, query: str, capabilities: Dict) -> bool:
        """匹配请求和 Agent 能力"""
        # 简单的关键词匹配
        agent_type = capabilities.get("type", "")
        agent_capabilities = capabilities.get("capabilities", [])
        
        # 根据 Agent 类型匹配
        if agent_type == "fast" and "快速" in query:
            return True
        
        # 根据 Agent 能力匹配
        if "tool_usage" in agent_capabilities and any(keyword in query for keyword in ["工具", "调用", "执行"]):
            return True
        
        if "memory" in agent_capabilities and any(keyword in query for keyword in ["记忆", "历史", "之前"]):
            return True
        
        return False


# 导入 asyncio
import asyncio
