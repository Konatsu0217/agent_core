import asyncio
import json
import uuid
from typing import Any

from clients import LLMClientManager
from clients.llm_client import static_llmClientManager
from clients.mcp_client import MCPHubClient
from clients.pe_client import PEClient
from core.agent_interface import IBaseAgent
from global_statics import global_config
from models.agent_data_models import AgentRequest, AgentResponse


class FastAgent(IBaseAgent):
    """快速 Agent 实现"""
    def __init__(self, name: str = "fast_agent", use_tools: bool = True):
        """初始化 Agent"""
        self.backbone_llm_client = static_llmClientManager.get_client()
        # 初始化mcp管理中心客户端
        self.mcpClient = MCPHubClient(global_config['mcphub_url'])
        # 初始化PE客户端并建立连接
        self.peClient = PEClient(global_config['pe_url'])

        self.use_tools = use_tools
        self.mcp_tool_cache = {}

    async def initialize(self):
        """初始化 Agent"""
        # pe ws连接
        try:
            await self.peClient.connect()
            print("✅ PE客户端连接已建立")
        except Exception as e:
            print(f"❌ PE客户端连接失败: {e}")
            return
        # mcp工具发现/缓存
        try:
            tools = await self.mcpClient.get_tools()
            self.mcp_tool_cache = tools
            print(f"✅ MCPHubClient 发现 {len(tools)} 个工具")
        except Exception as e:
            print(f"⚠️ MCPHubClient get_tools failed: {e}")
            self.mcp_tool_cache = {}

        pass

    async def process(self, request: AgentRequest) -> AgentResponse:
        """处理用户请求"""
        # 工具和pe
        messages, tools = await self.async_get_pe_and_mcp_tools(
            session_id=request.session_id,
            user_query=self.warp_query(request.query)
        )

        if self.use_tools:
            result = await self.run_with_tools(messages, tools)
        else :
            result = await self.run_basic(messages, tools)

        return AgentResponse(
            response=result,
            session_id=request.session_id
        )

    async def run_with_tools(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        MAX_STEPS = 10  # 防死循环

        for _ in range(MAX_STEPS):

            # === 启动一轮 LLM 流式输出 ===
            tool_call_found = False
            final_answer = None

            async for event in self.run_llm_with_tools(
                    self.backbone_llm_client,
                    messages,
                    tools
            ):
                # ======== 工具调用 ========
                if event["event"] == "tool_call":
                    tool_call_found = True
                    call = event["tool_call"]

                    # 1. 执行 MCP 工具
                    result = await self.mcpClient.call_tool(
                        id=call["id"],
                        type=call["type"],
                        function=call["function"],
                    )

                    # 2. 将工具结果加入 messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": json.dumps(result),
                    })

                    # 注意：不要 break —— event 的流要读完
                    continue

                # ======== 最终输出 ========
                elif event["event"] == "final_content":
                    final_answer = event["content"]
                    # 继续读流，但最终要退出大循环
                    continue

            # ========= 一轮流结束后 =========

            if tool_call_found:
                # 有工具调用 → 开启下一轮 LLM 运行
                # （messages 已经被 append 了）
                continue

            # 没有工具调用 → 直接返回最终答案
            return final_answer

        # 超出最大循环
        return {"error": "Exceeded max ReAct steps"}


    async def run_basic(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        return await self.backbone_llm_client.chat_completion(
            messages=messages,
            tools=tools
        )


    def get_capabilities(self) -> dict:
        """返回 Agent 能力描述"""
        return {
            "type": "fast",
            "description": "快速响应 Agent"
        }

    def estimate_cost(self, request: AgentRequest) -> dict:
        """估算成本"""
        return {
            "time": 99999,  # 100ms
            "tokens": 99999  # 假设每个请求 10 个 Token
        }

    async def async_get_pe_and_mcp_tools(self, session_id: str, user_query: str):
        # ✅ 统一创建 Task 对象
        pe_task = asyncio.create_task(self.peClient.build_prompt(
            session_id=session_id,
            user_query=user_query,
            request_id=str(uuid.uuid4()),
            stream=False
        ))

        # 空协程，用于占位
        async def empty_coroutine():
            return self.mcp_tool_cache

        if self.mcp_tool_cache is None:
            mcp_task = asyncio.create_task(self.mcpClient.get_tools())
        else:
            mcp_task = asyncio.create_task(empty_coroutine())

        # 并行执行
        try:
            results = await asyncio.wait_for(
                asyncio.gather(pe_task, mcp_task, return_exceptions=True),
                timeout=5
            )

            llm_request_response, self.mcp_tool_cache = results

            # ✅ 处理异常
            if isinstance(llm_request_response, Exception):
                print(f"❌ PE build_prompt failed: {llm_request_response}")
                return

            if isinstance(self.mcp_tool_cache, Exception):
                print(f"⚠️ MCPHubClient get_tools failed: {self.mcp_tool_cache}")
                self.mcp_tool_cache = []

            # ✅ 正确提取数据
            llm_request = llm_request_response.get('llm_request', {})
            messages = llm_request.get('messages', [])

            print(f"✅ PE build_prompt messages: {messages}")
            print(f"✅ Available tools: {self.mcp_tool_cache}")
            return messages, self.mcp_tool_cache

        except asyncio.TimeoutError:
            print("❌ Timeout: PE or MCP request took too long")
            return [], []
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return [], []
