import asyncio
from typing import List, Dict, Any
from src.di.services.interfaces.memory_service import IMemoryService

# 尝试导入 MemoryManager，如果失败则使用模拟实现
try:
    from src.infrastructure.clients.mem0ai_client import MemoryManager
    has_mem0 = True
except ImportError:
    has_mem0 = False
    print("⚠️ mem0 模块未安装，将使用模拟实现")


class Mem0MemoryService(IMemoryService):
    """基于 Mem0 的记忆服务"""
    
    def __init__(self):
        self.mem = MemoryManager()
    
    async def search(self, query: str, user_id: str, **kwargs) -> List[Dict[str, Any]]:
        """搜索记忆"""
        limit = kwargs.get("limit", 5)
        try:
            return await self.mem.search(query=query, user_id=user_id, limit=limit)
        except Exception as e:
            print(f"⚠️ Mem0Client search failed: {e}")
            return []
    
    async def add(self, messages: List[Dict[str, Any]], user_id: str) -> None:
        """添加记忆"""
        await asyncio.to_thread(self.mem.add, messages, user_id)
