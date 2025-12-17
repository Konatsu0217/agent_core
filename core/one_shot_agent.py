from core.abs_agent import IBaseAgent, ExecutionMode
from models import AgentRequest, AgentResponse


class OneShotAgent(IBaseAgent):
    """One-Shot Agent 实现"""
    def __init__(self,
                 work_flow_type: ExecutionMode = ExecutionMode.TEST,
                 name: str = "one_shot_agent",
                 use_tools: bool = True,
                 output_format: str = "json"):
        super().__init__(name=name, work_flow_type=work_flow_type, use_tools=use_tools, output_format=output_format)
        """初始化 Agent"""
        print("OneShotAgent Not Implemented")
        raise Exception("OneShotAgent Not Implemented")

    async def process(self, request: AgentRequest) -> AgentResponse:
        pass

    def warp_query(self, query: str) -> str:
        pass

    def get_capabilities(self) -> dict:
        pass

    def estimate_cost(self, request: AgentRequest) -> dict:
        pass

    def initialize(self):
        pass



