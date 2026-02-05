from abc import ABC, abstractmethod
from typing import List, Dict, Any


class IMemoryService(ABC):
    """记忆服务接口"""
    
    @abstractmethod
    async def search(self, query: str, user_id: str, **kwargs) -> List[Dict[str, Any]]:
        """搜索记忆"""
        pass
    
    @abstractmethod
    async def add(self, messages: List[Dict[str, Any]], user_id: str) -> None:
        """添加记忆"""
        pass
