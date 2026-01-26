from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class IContextMaker(ABC):
    """上下文构建接口"""
    
    @abstractmethod
    async def build_context(self, session_id: str, user_query: str, **kwargs) -> Dict[str, Any]:
        """构建上下文"""
        pass
    
    @abstractmethod
    async def augment_context(self, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """增强上下文"""
        pass


class DefaultContextMaker(IContextMaker):
    """默认上下文构建器"""
    
    def __init__(self, memory_service=None, tool_manager=None):
        self.memory_service = memory_service
        self.tool_manager = tool_manager
        self.augmenters = []
    
    def add_augmenter(self, augmenter):
        """添加上下文增强器"""
        self.augmenters.append(augmenter)
    
    async def build_context(self, session_id: str, user_query: str, **kwargs) -> Dict[str, Any]:
        """构建上下文"""
        context = {
            "session_id": session_id,
            "user_query": user_query,
            "messages": [],
            "tools": [],
            "memory": [],
            "session": None
        }
        
        # 增强上下文
        for augmenter in self.augmenters:
            context = await augmenter.augment(context, **kwargs)
        
        return context
    
    async def augment_context(self, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """增强上下文"""
        for augmenter in self.augmenters:
            context = await augmenter.augment(context, **kwargs)
        return context
