import asyncio
from src.agent.fast_agent import FastAgent
from src.coordinator.agent_coordinator import AgentCoordinator, TaskDispatcher
from src.di.container import get_service_container, get_injector
from src.config.config import ConfigManager
from src.domain.models.agent_data_models import AgentRequest


async def test_fast_agent_initialization():
    """测试 FastAgent 初始化"""
    print("=== 测试 FastAgent 初始化 ===")
    
    # 创建 FastAgent
    agent = FastAgent(name="test_fast_agent")
    
    # 初始化 Agent
    await agent.initialize()
    print("✅ FastAgent 初始化成功")
    
    # 测试获取能力描述
    capabilities = agent.get_capabilities()
    print(f"✅ 能力描述: {capabilities}")
    
    return agent


async def test_agent_coordinator():
    """测试 Agent 协调器"""
    print("\n=== 测试 Agent 协调器 ===")
    
    # 创建协调器
    coordinator = AgentCoordinator()
    
    # 创建并注册 FastAgent
    fast_agent = FastAgent(name="fast_agent")
    coordinator.register_agent(fast_agent)
    
    # 初始化所有 Agent
    await coordinator.initialize_all_agents()
    print("✅ 所有 Agent 初始化成功")
    
    # 创建任务分发器
    dispatcher = TaskDispatcher()
    coordinator.set_task_dispatcher(dispatcher)
    print("✅ 任务分发器设置成功")
    
    return coordinator


async def test_service_container():
    """测试服务容器"""
    print("\n=== 测试服务容器 ===")
    
    # 获取服务容器
    container = get_service_container()
    print("✅ 服务容器获取成功")
    
    # 测试注册和获取服务
    test_service = {"name": "test_service"}
    container.register("test_service", test_service)
    
    retrieved_service = container.get("test_service")
    if retrieved_service == test_service:
        print("✅ 服务注册和获取成功")
    else:
        print("❌ 服务注册和获取失败")
    
    return container


async def test_config_manager():
    """测试配置管理器"""
    print("\n=== 测试配置管理器 ===")
    
    # 创建配置管理器
    config_manager = ConfigManager()
    print("✅ 配置管理器创建成功")
    
    # 获取服务配置
    service_config = config_manager.get_service_config()
    print("✅ 服务配置获取成功")
    
    # 获取 Agent 配置
    agent_config = config_manager.get_agent_config("fast_agent")
    print("✅ Agent 配置获取成功")
    
    return config_manager


async def test_full_workflow():
    """测试完整工作流程"""
    print("\n=== 测试完整工作流程 ===")
    
    # 创建协调器
    coordinator = AgentCoordinator()
    
    # 创建并注册 FastAgent
    fast_agent = FastAgent(name="fast_agent")
    coordinator.register_agent(fast_agent)
    
    # 初始化所有 Agent
    await coordinator.initialize_all_agents()
    
    # 创建测试请求
    request = AgentRequest(
        query="你好，今天天气怎么样？",
        session_id="test_session_123",
        extraInfo={"add_memory": True}
    )
    
    # 处理请求
    print("处理请求:", request.query)
    response = await coordinator.process_request(request)
    print(f"✅ 请求处理完成，响应: {response.response}")
    
    return response


async def main():
    """主测试函数"""
    print("开始测试模块化架构...\n")
    
    # 运行所有测试
    await test_fast_agent_initialization()
    await test_agent_coordinator()
    await test_service_container()
    await test_config_manager()
    await test_full_workflow()
    
    print("\n=== 所有测试完成 ===")


if __name__ == "__main__":
    asyncio.run(main())
