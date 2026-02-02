import asyncio
import datetime
import time

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
    # container.register("memory_service", Mem0MemoryService())
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
        query=f"你帮我上网查一下明天深圳天气怎么样嘛",
        session_id="test_session_123",
        extraInfo={"add_memory": True}
    )

    pipe = await basic_agent.process(test_request)

    collected = []
    async for event in pipe.reader():
        if event["type"] == "text_delta":
            chunk = event["payload"]["text"]
            collected.append(chunk)
            print(f"\033[31m{chunk}\033[0m", end="", flush=True)
        elif event["type"] == "tool_call":
            # 这里可以直接先返回一个气泡
            pass
        elif event["type"] == "tool_result":
            pass
        elif event["type"] == "final":
            pass

    print()



if __name__ == "__main__":
    asyncio.run(test_agent_factory())
