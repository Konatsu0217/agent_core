```python
async def best_way():
    # 初始化服务容器
    from src.di.container import get_service_container
    from src.di.services.impl.default_query_wrapper_service import DefaultQueryWrapper
    from src.di.services.impl.mcp_tool_manager import McpToolManager
    from src.di.services.impl.mem0_memory_service import Mem0MemoryService
    from src.di.services.impl.pe_prompt_service import PePromptService
    from src.di.services.impl.default_session_service import DefaultSessionService

    from src.agent.agent_factory import AgentFactory

    from src.main import AgentRequest

    from src.infrastructure.utils.pipe import ProcessPipe

    print("=== Step 0: 创建服务的容器，注册必备的服务 ===")
    # 获取服务容器
    container = get_service_container()

    # 注册服务
    container.register("query_wrapper", DefaultQueryWrapper())
    container.register("tool_manager", McpToolManager())
    container.register("memory_service", Mem0MemoryService())
    container.register("prompt_service", PePromptService())
    container.register("session_service", DefaultSessionService())
    print("✅ 所有服务注册完成")

    print("=== Step 1: 创建基础Fast Agent ===")
    basic_agent = await AgentFactory.get_basic_agent()
    print(f"Agent 类型: {type(basic_agent).__name__}")
    print(f"Agent 名称: {basic_agent.name}")
    print(f"是否使用工具: {basic_agent.use_tools}")
    print(f"工作流类型: {basic_agent.work_flow_type}")
    print(f"输出格式: {basic_agent.output_format}")
    print(f"需要的服务: {basic_agent.services_needed}")
    print(f"能力描述: {basic_agent.get_capabilities()}")

    print("=== Step 2: 进行Agent的初始化 ===")
    await basic_agent.initialize()

    print("=== Step 3: 构造请求体 ===")
    # 测试处理请求
    test_request = AgentRequest(
        query=f"把我目录下的'.env.example'文件删了",
        session_id="test_session_123"
    )

    print("=== Step 4: 监听管道内事件 ===")
    pipe = ProcessPipe()
    await basic_agent.process(test_request, pipe)

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
            # 工具调用审批
            payload = event["payload"]
            approval_id = payload.get("approval_id", "")
            await approve_tool(payload, pipe, approval_id)
        elif event["type"] == "approval_decision":
            pass


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

```
