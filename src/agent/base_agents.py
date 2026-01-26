import asyncio
import json
from typing import Any, Dict, List, Optional
from src.agent.abs_agent import IBaseAgent, run_llm_with_tools, ExecutionMode
from src.infrastructure.clients.llm_clients.llm_client_manager import static_llmClientManager


class BaseAgent(IBaseAgent):
    """基础 Agent 实现"""
    
    def __init__(self, name: str, work_flow_type: ExecutionMode, use_tools: bool = True, output_format: str = "json"):
        super().__init__(name=name, work_flow_type=work_flow_type, use_tools=use_tools, output_format=output_format)
        self.backbone_llm_client = static_llmClientManager.get_client()
        self.context_maker = None
    
    def set_context_maker(self, context_maker):
        """设置上下文构建器"""
        self.context_maker = context_maker
    
    async def initialize(self):
        """初始化 Agent"""
        pass

    async def process(self, request):
        """处理用户请求"""
        # 子类需要实现此方法
        return None

    def get_capabilities(self) -> dict:
        """返回 Agent 能力描述"""
        return {
            "type": "base",
            "description": "基础 Agent"
        }

    def estimate_cost(self, request) -> dict:
        """估算成本"""
        return {
            "time": 99999,
            "tokens": 99999
        }


class ToolUsingAgent(BaseAgent):
    """支持工具使用的 Agent"""
    
    def __init__(self, name: str, work_flow_type: ExecutionMode, use_tools: bool = True, output_format: str = "json"):
        super().__init__(name=name, work_flow_type=work_flow_type, use_tools=use_tools, output_format=output_format)
        self.tool_manager = None
    
    def set_tool_manager(self, tool_manager):
        """设置工具管理器"""
        self.tool_manager = tool_manager
    
    async def run_with_tools(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> str:
        """使用工具运行"""
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

                    # 1. 执行工具
                    if self.tool_manager:
                        result = await self.tool_manager.call_tool(call)
                    else:
                        result = {"success": False, "error": "No tool manager set"}

                    # 2. 将工具结果加入 messages
                    if result.get("success") is False:
                        messages.append({
                            "role": "user",
                            "content": f"工具调用 {call['id']} 失败：{result.get('error', '')}"
                        })
                        continue

                    msg = result.get("result", {}).get("data", "")
                    await self.append_tool_call(messages, call, msg)
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
                continue

            # 没有工具调用 → 直接返回最终答案
            return final_answer

        # 超出最大循环
        return "{\"error\": \"Exceeded max ReAct steps\"}"

    @staticmethod
    async def append_tool_call(messages, call, msg):
        """添加工具调用结果到消息列表"""
        # 先插入 tool 消息
        messages.append({
            "role": "tool",
            "tool_call_id": call["id"],
            "content": msg,
        })
        # 再插入 assistant(tool_call) 消息
        messages.insert(-1, {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": call["id"],
                    "type": "function",
                    "function": {
                        "name": call["function"]["name"],
                        "arguments": json.dumps(call["function"]["arguments"])
                    }
                }
            ]
        })


class MemoryAwareAgent(BaseAgent):
    """支持记忆管理的 Agent"""
    
    def __init__(self, name: str, work_flow_type: ExecutionMode, use_tools: bool = True, output_format: str = "json"):
        super().__init__(name=name, work_flow_type=work_flow_type, use_tools=use_tools, output_format=output_format)
        self.memory_service = None
        self.response_cache: Dict[str, str] = {}
    
    def set_memory_service(self, memory_service):
        """设置记忆服务"""
        self.memory_service = memory_service
    
    async def add_memory(self, session_id: str) -> None:
        """添加记忆"""
        if not self.memory_service:
            return
        
        messages = [{
            "role": "user",
            "content": self.response_cache.get("query", "")
        }, {
            "role": "assistant",
            "content": self.response_cache.get("response", "")
        }]
        self.response_cache.clear()
        await self.memory_service.add(messages, session_id)
