from typing import Dict, Optional, List, Any
from src.domain.models.agent_data_models import AgentRequest, AgentResponse


class AgentCoordinator:
    """Agent 协调器"""
    
    def __init__(self):
        self.agents: Dict[str, Any] = {}
        self.task_dispatcher: Optional[TaskDispatcher] = None
    
    def register_agent(self, agent):
        """注册 Agent"""
        self.agents[agent.name] = agent
    
    def get_agent(self, agent_name: str) -> Optional[Any]:
        """获取 Agent"""
        return self.agents.get(agent_name)
    
    def set_task_dispatcher(self, task_dispatcher):
        """设置任务分发器"""
        self.task_dispatcher = task_dispatcher
    
    async def process_request(self, request: AgentRequest, agent_name: Optional[str] = None) -> AgentResponse:
        """处理请求"""
        # 如果指定了 Agent，直接使用
        if agent_name:
            agent = self.get_agent(agent_name)
            if not agent:
                return AgentResponse(
                    response={"error": f"Agent {agent_name} not found"},
                    session_id=request.session_id
                )
            return await agent.process(request)
        
        # 否则使用任务分发器选择 Agent
        if self.task_dispatcher:
            selected_agent = await self.task_dispatcher.select_agent(request, self.agents)
            if selected_agent:
                return await selected_agent.process(request)
        
        # 默认使用第一个 Agent
        if self.agents:
            default_agent = next(iter(self.agents.values()))
            return await default_agent.process(request)
        
        return AgentResponse(
            response={"error": "No agents available"},
            session_id=request.session_id
        )
    
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
