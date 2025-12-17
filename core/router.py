from clients.llm_client import static_llmClientManager
from core.agent_manager import AgentWrapper


class AgentRouter:
    def __init__(self):
        # router不太一样，不需要LLM，返回我希望应该只有一个分类头，不然对响应速度纯粹的负面效果
        self.router_client = None

    def choose_agent(self, query: str, agent_dict: dict[str, AgentWrapper]) -> AgentWrapper:
        pass
