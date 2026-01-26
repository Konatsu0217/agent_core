import json
from abc import ABC, abstractmethod
from enum import Enum

from src.domain.models.agent_data_models import AgentRequest, AgentResponse


async def run_llm_with_tools(llm_client, messages, tools):
    buffer_delta = {"role": None, "content": []}
    tool_call_accumulator = {}

    current_type = None
    current_tool_name = None
    tool_call_id = None

    async for raw in llm_client.chat_completion_stream(
            messages=messages,
            tools=tools
    ):
        data = json.loads(raw)
        delta = data["choices"][0]["delta"]
        finish_reason = data["choices"][0]["finish_reason"]

        # ==== Role ====
        if delta.get("role") and not buffer_delta["role"]:
            buffer_delta["role"] = delta["role"]

        # ==== Content ====
        if delta.get("content"):
            print(delta["content"], end="", flush=True)
            buffer_delta["content"].append(delta["content"])

        # ==== Tool Calls ====
        if delta.get("tool_calls"):
            for call in delta["tool_calls"]:
                cid = call["id"]
                if tool_call_id is None:
                    tool_call_id = cid
                if cid not in tool_call_accumulator:
                    if current_type is None:
                        current_type = call["type"]
                    if current_tool_name is None:
                        current_tool_name = call["function"]["name"]
                    tool_call_accumulator[cid] = {
                        "id": tool_call_id,
                        "type": call["type"],
                        "function": {
                            "name": call["function"]["name"],
                            "arguments": ""
                        }
                    }

                # 拼接 JSON 字符串片段
                if call["function"]["arguments"]:
                    tool_call_accumulator[cid]["function"]["arguments"] += call["function"]["arguments"]

                try:
                    args = tool_call_accumulator[cid]["function"]["arguments"]
                    parsed = json.loads(args)
                    # 如果成功解析 → yield 出去让外部执行
                    # messages.append(response.choices[0].message)
                    yield {
                        "event": "tool_call",
                        "tool_call": {
                            "id": tool_call_id,
                            "type": current_type,
                            "function": {
                                "name": current_tool_name,
                                "arguments": parsed
                            }
                        }
                    }
                    # 这个调用已经发出去，不要再重复 yield
                    del tool_call_accumulator[cid]
                    current_tool_name = None
                    current_type = None
                    tool_call_id = None
                except:
                    pass  # JSON 还没拼完，继续流式等下一段

        # ==== 流结束 ====
        if finish_reason:
            yield {
                "event": "final_content",
                "role": buffer_delta["role"],
                "content": "".join(buffer_delta["content"]),
            }
            return

class ExecutionMode(Enum):
    TEST = "test"
    ONE_SHOT = "one-shot"
    REACT = "ReAct"
    PLAN_AND_SOLVE = "Plan-and-Solve"


class IBaseAgent(ABC):
    """所有 Agent 的统一接口"""
    def __init__(self, name: str, work_flow_type: ExecutionMode, use_tools: bool = True, output_format: str = "json"):
        # Agent 名称
        self.name = name
        # 工作模式：one-shot / ReAct / Plan-and-Solve
        self.work_flow_type = work_flow_type
        # 是否启用工具
        self.use_tools = use_tools
        # 是否格式化输出，如果有格式化输出自己处理格式解析
        self.output_format = output_format

    @abstractmethod
    def initialize(self):
        """初始化 Agent"""
        pass

    @abstractmethod
    async def process(self, request: AgentRequest) -> AgentResponse:
        """处理用户请求，默认过程中流式，最终结果非流式"""
        pass

    @abstractmethod
    def get_capabilities(self) -> dict:
        """返回 Agent 能力描述（用于 Decider 决策）"""
        pass

    @abstractmethod
    def estimate_cost(self, request: AgentRequest) -> dict:
        """估算处理该请求的成本（时间/Token）"""
        pass
