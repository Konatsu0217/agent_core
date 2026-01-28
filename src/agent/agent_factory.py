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
