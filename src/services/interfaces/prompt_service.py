from abc import ABC, abstractmethod
from typing import Dict, Any


class IPromptService(ABC):
    """提示词服务接口"""
    
    @abstractmethod
    async def initialize(self):
        """初始化提示词服务"""
        pass
    
    @abstractmethod
    async def build_prompt(self, session_id: str, user_query: str, **kwargs) -> Dict[str, Any]:
        """构建提示词"""
        pass
