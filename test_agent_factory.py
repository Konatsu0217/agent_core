import asyncio
from time import sleep

from src.agent.agent_factory import AgentFactory
from src.coordinator.agent_coordinator import AgentCoordinator
from src.domain.models.agent_data_models import AgentRequest
from src.infrastructure.utils.pipe import ProcessPipe


async def test_agent_factory():
    """测试 AgentFactory 创建不同类型的 Agent"""
    coordinator = AgentCoordinator()

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

    coordinator.register_agent(basic_agent)

    # 测试处理请求
    test_request = AgentRequest(
        query=f"使用命令行工具获取bilibili的今日热榜前十，写到txt文件里",
        session_id="test_session_123"
    )

    pipe = ProcessPipe()
    await coordinator.process_request(test_request, pipe)

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
        elif event["type"] == "approval_required":
            payload = event["payload"]
            approval_id = payload.get("approval_id", "")
            await approve_tool(payload, pipe, approval_id)
        elif event["type"] == "approval_decision":
            pass

    await pipe.close()
    await asyncio.sleep(20)


async def approve_tool(payload, pipe, approval_id):
    print("\n🔔 工具需要审批:")
    print(f"   审批ID: {payload.get("approval_id")}")
    print(f"   工具: {payload.get("name")}")
    print(f"   参数: {payload.get("arguments")}")
    print(f"   安全评估: {payload.get('safety_assessment', {})}")
    print(f"   消息: {payload.get('message', '')}")

    while True:
        choice = input("\n请选择操作 (1-批准, 2-拒绝): ")
        if choice == "1":
            await pipe.approval_decision(approval_id, "approved")
            return
        else:
            await pipe.approval_decision(approval_id, "rejected")
            return


if __name__ == "__main__":
    asyncio.run(test_agent_factory())
