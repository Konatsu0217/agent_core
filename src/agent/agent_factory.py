import json
import os
from typing import Dict, Any

from src.agent.abs_agent import IBaseAgent, ExecutionMode
from src.agent.base_agents import CombinedAgent, ToolOnlyAgent, \
    MemoryOnlyAgent, BasicAgent


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
        agent_type = agent_profile.get("agent_type", "BasicAgent")

        # 使用工厂映射而不是硬编码
        agent_constructors = {
            "basic": BasicAgent,
            "tool_only": ToolOnlyAgent,
            "memory_only": MemoryOnlyAgent,
            "combined": CombinedAgent,
        }

        constructor = agent_constructors.get(agent_type, BasicAgent)
        work_flow_type = ExecutionMode(agent_profile.get("work_flow_type", "test"))
        return constructor(agent_profile, work_flow_type)

    @staticmethod
    async def get_basic_agent() -> IBaseAgent:
        """
        获取基础 Agent 实例
        
        Args:
            agent_profile: Agent 配置文件
            
        Returns:
            基础 Agent 实例
        """
        basic_profile = await AgentFactory.get_basic_agent_profile()
        agent =  AgentFactory.create_agent(basic_profile)
        return agent

    @staticmethod
    async def get_basic_agent_profile() -> Dict[str, Any]:
        """
        获取基础 Agent 配置文件
        默认读取 agent/agent_profiles/fast_agent_profile.json
        
        Returns:
            Agent 配置文件
        """
        profile_path = os.path.join(
            os.path.dirname(__file__),
            'agent_profiles',
            'fast_agent_profile.json'
        )
        with open(profile_path, 'r', encoding='utf-8') as f:
            return json.load(f)
