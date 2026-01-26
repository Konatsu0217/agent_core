from typing import Dict, Any


class MemoryAugmenter:
    """记忆增强器"""
    
    def __init__(self, memory_service):
        self.memory_service = memory_service
    
    async def augment(self, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """增强上下文"""
        if not self.memory_service:
            return context
        
        session_id = context.get("session_id")
        user_query = context.get("user_query")
        
        if session_id and user_query:
            # 搜索相关记忆
            memory = await self.memory_service.search(
                query=user_query,
                user_id=session_id,
                limit=kwargs.get("memory_limit", 5)
            )
            context["memory"] = memory
            
            # 将记忆添加到消息中
            if memory:
                memory_content = "\n\n[Relevant Memory]: " + " ".join([m.get("content", "") for m in memory]) + " \n\n"
                if context["messages"]:
                    context["messages"][0]["content"] += memory_content
        
        return context
