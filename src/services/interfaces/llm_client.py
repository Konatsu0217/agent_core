from abc import ABC, abstractmethod
from typing import List, Dict, Any, AsyncGenerator


class ILLMClient(ABC):
    """LLM 客户端接口"""
    
    @abstractmethod
    async def chat_completion_stream(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]] = None, **kwargs) -> AsyncGenerator[str, None]:
        """流式聊天完成"""
        pass
    
    @abstractmethod
    async def chat_completion(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """聊天完成"""
        pass
