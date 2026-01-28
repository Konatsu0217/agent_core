import asyncio
from src.agent.agent_factory import AgentFactory
from src.domain.models.agent_data_models import AgentRequest

async def test_agent_factory():
    """测试 AgentFactory 创建不同类型的 Agent"""
    
    print("=== 测试 1: 创建基础 Agent (不使用工具和记忆) ===")
    basic_profile = {
        "name": "basic_agent_test",
        "tools_use": False,
        "memory": False,
        "role": "基础测试角色",
        "description": "这是一个基础测试agent",
        "agent_id": "basic_agent_test_123"
    }
    basic_agent = AgentFactory.create_agent(basic_profile)
    print(f"Agent 类型: {type(basic_agent).__name__}")
    print(f"Agent 名称: {basic_agent.name}")
    print(f"是否使用工具: {basic_agent.use_tools}")
    print(f"能力描述: {basic_agent.get_capabilities()}")
    await basic_agent.initialize()
    
    # 测试处理请求
    test_request = AgentRequest(
        query="你好，基础agent",
        session_id="test_session_123",
        extraInfo={"add_memory": True}
    )
    response = await basic_agent.process(test_request)
    print(f"响应结果: {response}")
    print()
    
    print("=== 测试 2: 创建只使用工具的 Agent ===")
    tool_only_profile = {
        "name": "tool_only_agent_test",
        "tools_use": True,
        "memory": False,
        "role": "工具测试角色",
        "description": "这是一个只使用工具的测试agent",
        "agent_id": "tool_only_agent_test_123"
    }
    tool_only_agent = AgentFactory.create_agent(tool_only_profile)
    print(f"Agent 类型: {type(tool_only_agent).__name__}")
    print(f"Agent 名称: {tool_only_agent.name}")
    print(f"是否使用工具: {tool_only_agent.use_tools}")
    print(f"能力描述: {tool_only_agent.get_capabilities()}")
    await tool_only_agent.initialize()
    
    # 测试处理请求
    response = await tool_only_agent.process(test_request)
    print(f"响应结果: {response}")
    print()
    
    print("=== 测试 3: 创建只使用记忆的 Agent ===")
    memory_only_profile = {
        "name": "memory_only_agent_test",
        "tools_use": False,
        "memory": True,
        "role": "记忆测试角色",
        "description": "这是一个只使用记忆的测试agent",
        "agent_id": "memory_only_agent_test_123"
    }
    memory_only_agent = AgentFactory.create_agent(memory_only_profile)
    print(f"Agent 类型: {type(memory_only_agent).__name__}")
    print(f"Agent 名称: {memory_only_agent.name}")
    print(f"是否使用工具: {memory_only_agent.use_tools}")
    print(f"能力描述: {memory_only_agent.get_capabilities()}")
    await memory_only_agent.initialize()
    
    # 测试处理请求
    response = await memory_only_agent.process(test_request)
    print(f"响应结果: {response}")
    print()
    
    print("=== 测试 4: 创建同时使用工具和记忆的 Agent ===")
    combined_profile = {
        "name": "combined_agent_test",
        "tools_use": True,
        "memory": True,
        "role": "综合测试角色",
        "description": "这是一个同时使用工具和记忆的测试agent",
        "agent_id": "combined_agent_test_123"
    }
    combined_agent = AgentFactory.create_agent(combined_profile)
    print(f"Agent 类型: {type(combined_agent).__name__}")
    print(f"Agent 名称: {combined_agent.name}")
    print(f"是否使用工具: {combined_agent.use_tools}")
    print(f"能力描述: {combined_agent.get_capabilities()}")
    await combined_agent.initialize()
    
    # 测试处理请求
    response = await combined_agent.process(test_request)
    print(f"响应结果: {response}")
    print()
    
    print("=== 所有测试完成 ===")

if __name__ == "__main__":
    asyncio.run(test_agent_factory())
