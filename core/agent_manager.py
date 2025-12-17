import json
import uuid
from re import match
from typing import Optional

from core.abs_agent import IBaseAgent, ExecutionMode
from core.fast_agent import FastAgent
from core.one_shot_agent import OneShotAgent
from core.plan_and_solve_agent import PlanAndSolveAgent
from core.react_agent import ReactAgent


# 管理所有 Agent 实例, router会读取这个dict来调度不同的agent
class AgentManager:
    def __init__(self):
        self.agent_dict: dict[str, AgentWrapper] = {}
        self.router


    async def create_agent(self, name: str, work_flow_type: ExecutionMode = ExecutionMode.ONE_SHOT,
                           use_tools: bool = True, output_format: str = "json") -> IBaseAgent:
        """
           除了初始化的时候以外，都不要调用
        """

        agent : Optional[IBaseAgent] = None
        match work_flow_type.value:
            case ExecutionMode.TEST:
                agent = FastAgent(name=name, work_flow_type=work_flow_type, use_tools=use_tools, output_format=output_format)
            case ExecutionMode.ONE_SHOT.value:
                agent = OneShotAgent(name=name, work_flow_type=work_flow_type, use_tools=use_tools, output_format=output_format)
            case ExecutionMode.REACT.value:
                agent = ReactAgent(name=name, work_flow_type=work_flow_type, use_tools=use_tools, output_format=output_format)
            case ExecutionMode.PLAN_AND_SOLVE.value:
                agent = PlanAndSolveAgent(name=name, work_flow_type=work_flow_type, use_tools=use_tools, output_format=output_format)

        if agent is None:
             raise ValueError(f"Unsupported work_flow_type: {work_flow_type.value}")

        self.agent_dict[agent_uid] = AgentWrapper(agent=agent, schema=schema)

        return agent


class AgentWrapper:
    def __init__(self, agent: IBaseAgent, schema: str):
        self.agent = agent
        self.schema = schema


if __name__ == "__main__":
    agent = AgentManager()