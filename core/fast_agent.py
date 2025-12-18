import asyncio
import json
import logging
import uuid
from pyexpat.errors import messages
from typing import Any, Optional

from clients.llm_client import static_llmClientManager
from clients.mcp_client import MCPHubClient
from clients.mem0ai_client import MemoryManager
from clients.pe_client import PEClient
from core.agent_interface import IBaseAgent, run_llm_with_tools
from global_statics import global_config
from models.agent_data_models import AgentRequest, AgentResponse


class FastAgent(IBaseAgent):
    """快速 Agent 实现"""

    def __init__(self, extra_prompt: Optional[str] = None, name: str = "fast_agent", use_tools: bool = True):
        """初始化 Agent"""
        self.extra_prompt: Optional[str] = extra_prompt

        self.backbone_llm_client = static_llmClientManager.get_client()
        # 初始化mcp管理中心客户端
        self.mcpClient = MCPHubClient(base_url=f"{global_config['mcphub_url']}:{global_config['mcphub_port']}")
        # 初始化PE客户端并建立连接
        self.peClient = PEClient(global_config['pe_url'])

        # 聊天内容的后处理，先返回再异步处理tts等后续工作
        self.response_cache: dict[str, str] = {}

        self.mem = MemoryManager()

        self.use_tools = use_tools
        self.mcp_tool_cache = []

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

    def warp_query(self, query: str) -> str:
        """包装用户查询，添加必要的上下文"""
        return f"用户查询: {query}, system: 你的回复必须为json格式{{'response': '你的回复','action': '简短、精准地表述你要做的肢体动作，使用英文','expression': '从我为你提供的tool_type = resource中选择表情(可选，如果未提供则为空字符串)'}}"

    async def process(self, request: AgentRequest) -> AgentResponse:
        """处理用户请求"""
        # 工具和pe
        messages, tools = await self.async_get_pe_and_mcp_tools(
            session_id=request.session_id,
            user_query=self.warp_query(request.query),
            extra_prompt=self.extra_prompt if self.extra_prompt is not None else "",
        )

        if self.use_tools:
            result = await self.run_with_tools(messages, tools)
        else:
            result = await self.run_basic(messages, tools)

        result_json = json.loads(result)
        # 用来存聊天记录
        self.response_cache['query'] = request.query
        self.response_cache['response'] = result_json.get('response', '')
        self.response_cache['action'] = result_json.get('action', '')
        self.response_cache['expression'] = result_json.get('expression', '')

        asyncio.create_task(self.add_memory(request.session_id))

        return AgentResponse(
            response=result_json,
            session_id=request.session_id
        )

    async def add_memory(self, session_id: str) -> None:
        messages = [{
            "role": "user",
            "content": self.response_cache['query']
        }, {
            "role": "assistant",
            "content": self.response_cache['response']
        }]
        logging.info(f"add memory: {messages}")
        loop = asyncio.get_running_loop()
        loop.run_in_executor(
            None,  # 默认 ThreadPoolExecutor
            self.mem.add,
            messages,
            session_id
        )

    async def run_with_tools(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        MAX_STEPS = 10  # 防死循环

        for _ in range(MAX_STEPS):

            # === 启动一轮 LLM 流式输出 ===
            tool_call_found = False
            final_answer = None

            async for event in run_llm_with_tools(
                    self.backbone_llm_client,
                    messages,
                    tools
            ):
                # ======== 工具调用 ========
                if event["event"] == "tool_call":
                    tool_call_found = True
                    call = event["tool_call"]
                    print(f"❕发现工具调用: {call}")

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
        final_answer = None
        async for event in run_llm_with_tools(
                self.backbone_llm_client,
                messages,
                tools
        ):
            # ======== 最终输出 ========
            if event["event"] == "final_content":
                final_answer = event["content"]
                continue

        return final_answer

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

    async def async_get_pe_and_mcp_tools(self, session_id: str, user_query: str, extra_prompt: str = ''):
        # ✅ 统一创建 Task 对象
        tasks = []

        pe_task = asyncio.create_task(self.peClient.build_prompt(
            session_id=session_id,
            user_query=user_query,
            request_id=str(uuid.uuid4()),
            system_resources=extra_prompt,
            stream=False
        ))

        tasks.append(pe_task)

        rag_task = asyncio.create_task(self.mem.search(query=user_query, user_id=session_id, limit=5))

        tasks.append(rag_task)

        # 空协程，用于占位
        async def empty_coroutine():
            return self.mcp_tool_cache

        if len(self.mcp_tool_cache) == 0:
            tasks.append(self.mcpClient.get_tools())
        else:
            tasks.append(empty_coroutine())

        # 并行执行
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=5
            )

            llm_request_response, rag_results, self.mcp_tool_cache = results

            # ✅ 处理异常
            if isinstance(llm_request_response, Exception):
                print(f"❌ PE build_prompt failed: {llm_request_response}")
                return

            if isinstance(self.mcp_tool_cache, Exception):
                print(f"⚠️ MCPHubClient get_tools failed: {self.mcp_tool_cache}")
                self.mcp_tool_cache = []
                return

            if isinstance(rag_results, Exception):
                print(f"⚠️ Mem0Client search failed: {rag_results}")
                rag_results = []
                return

            # ✅ 正确提取数据
            llm_request = llm_request_response.get('llm_request', {})
            messages = llm_request.get('messages', [])

            if rag_results:
                messages[0]['content'] += f"\n\n[Relevant Memory]: {rag_results} \n\n"

            print(f"✅ PE build_prompt messages: {messages}")
            print(f"✅ Available tools: {self.mcp_tool_cache}")
            return messages, self.mcp_tool_cache

        except asyncio.TimeoutError:
            print("❌ Timeout: PE or MCP request took too long")
            return [], []
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return [], []
