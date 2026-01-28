import asyncio
from src.agent.agent_factory import AgentFactory
from src.domain.models.agent_data_models import AgentRequest

async def test_agent_factory():
    """测试 AgentFactory 创建不同类型的 Agent"""
    
    # 初始化服务容器
    from src.di.container import get_service_container
    from src.services.impl.default_query_wrapper_service import DefaultQueryWrapper
    from src.services.impl.mcp_tool_manager import McpToolManager
    from src.services.impl.mem0_memory_service import Mem0MemoryService
    from src.services.impl.pe_prompt_service import PePromptService
    from src.services.impl.default_session_service import DefaultSessionService
    
    # 获取服务容器
    container = get_service_container()
    
    # 注册服务
    container.register("query_wrapper", DefaultQueryWrapper())
    container.register("tool_manager", McpToolManager())
    container.register("memory_service", Mem0MemoryService())
    container.register("prompt_service", PePromptService())
    container.register("session_service", DefaultSessionService())
    print("✅ 所有服务注册完成")
    
    print("=== 测试 1: 创建基础Fast Agent===")
    basic_agent = await AgentFactory.get_basic_agent()
    print(f"Agent 类型: {type(basic_agent).__name__}")
    print(f"Agent 名称: {basic_agent.name}")
    print(f"是否使用工具: {basic_agent.use_tools}")
    print(f"工作流类型: {basic_agent.work_flow_type}")
    print(f"输出格式: {basic_agent.output_format}")
    print(f"需要的服务: {basic_agent.services_needed}")
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
        "work_flow_type": "test",
        "output_format": "json",
        "services_needed": [["tool_manager", None],["prompt_service", None]],
        "role": "工具测试角色",
        "description": "这是一个只使用工具的测试agent",
        "agent_id": "tool_only_agent_test_123"
    }
    tool_only_agent = AgentFactory.create_agent(tool_only_profile)
    print(f"Agent 类型: {type(tool_only_agent).__name__}")
    print(f"Agent 名称: {tool_only_agent.name}")
    print(f"是否使用工具: {tool_only_agent.use_tools}")
    print(f"工作流类型: {tool_only_agent.work_flow_type}")
    print(f"输出格式: {tool_only_agent.output_format}")
    print(f"需要的服务: {tool_only_agent.services_needed}")
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
        "work_flow_type": "test",
        "output_format": "text",
        "services_needed": [["memory_service", None]],
        "role": "记忆测试角色",
        "description": "这是一个只使用记忆的测试agent",
        "agent_id": "memory_only_agent_test_123"
    }
    memory_only_agent = AgentFactory.create_agent(memory_only_profile)
    print(f"Agent 类型: {type(memory_only_agent).__name__}")
    print(f"Agent 名称: {memory_only_agent.name}")
    print(f"是否使用工具: {memory_only_agent.use_tools}")
    print(f"工作流类型: {memory_only_agent.work_flow_type}")
    print(f"输出格式: {memory_only_agent.output_format}")
    print(f"需要的服务: {memory_only_agent.services_needed}")
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
        "work_flow_type": "test",
        "output_format": "json",
        "services_needed": [["tool_manager", None], ["memory_service", None],["query_wrapper", None]],
        "role": "综合测试角色",
        "description": "这是一个同时使用工具和记忆的测试agent",
        "agent_id": "combined_agent_test_123"
    }
    combined_agent = AgentFactory.create_agent(combined_profile)
    print(f"Agent 类型: {type(combined_agent).__name__}")
    print(f"Agent 名称: {combined_agent.name}")
    print(f"是否使用工具: {combined_agent.use_tools}")
    print(f"工作流类型: {combined_agent.work_flow_type}")
    print(f"输出格式: {combined_agent.output_format}")
    print(f"需要的服务: {combined_agent.services_needed}")
    print(f"能力描述: {combined_agent.get_capabilities()}")
    await combined_agent.initialize()
    
    # 测试处理请求
    response = await combined_agent.process(test_request)
    print(f"响应结果: {response}")
    print()
    
    print("=== 测试 5: 使用默认参数创建 Agent ===")
    minimal_profile = {
        "name": "minimal_agent_test"
        # 其他参数使用默认值
    }
    minimal_agent = AgentFactory.create_agent(minimal_profile)
    print(f"Agent 类型: {type(minimal_agent).__name__}")
    print(f"Agent 名称: {minimal_agent.name}")
    print(f"是否使用工具: {minimal_agent.use_tools}")
    print(f"工作流类型: {minimal_agent.work_flow_type}")
    print(f"输出格式: {minimal_agent.output_format}")
    print(f"需要的服务: {minimal_agent.services_needed}")
    print(f"能力描述: {minimal_agent.get_capabilities()}")
    await minimal_agent.initialize()
    print()
    
    print("=== 所有测试完成 ===")

if __name__ == "__main__":
    asyncio.run(test_agent_factory())
