from abc import ABC, abstractmethod
from typing import Optional

from src.domain.agent_data_models import AgentRequest
from src.infrastructure.utils.pipe import ProcessPipe


class WorkflowEngine(ABC):
    """工作流引擎接口 - AgentCoordinator 需要实现这个"""

    @abstractmethod
    async def process(
            self,
            request: AgentRequest,
            pipe: ProcessPipe,
            agent_id: Optional[str] = None
    ) -> None:
        """
        处理请求并将事件写入 pipe

        Args:
            request: 标准化请求
            pipe: 事件管道
            agent_id: 可选的指定 agent
        """
        pass
