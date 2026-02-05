from abc import ABC, abstractmethod
from typing import List, Dict, Any


class IToolManager(ABC):
    """工具管理接口"""
    
    @abstractmethod
    async def initialize(self):
        """初始化工具管理器"""
        pass
    
    @abstractmethod
    async def get_tools(self) -> List[Dict[str, Any]]:
        """获取可用工具列表"""
        pass
    
    @abstractmethod
    async def call_tool(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """调用工具"""
        pass
