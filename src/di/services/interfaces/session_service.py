from abc import ABC, abstractmethod
from typing import Dict, Any


class ISessionService(ABC):
    """会话服务接口"""
    
    @abstractmethod
    async def get_session(self, session_id: str, agent_id: str) -> Dict[str, Any]:
        """获取会话信息"""
        pass
