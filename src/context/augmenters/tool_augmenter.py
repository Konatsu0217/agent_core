from typing import Dict, Any


class ToolAugmenter:
    """工具增强器"""
    
    def __init__(self, tool_manager):
        self.tool_manager = tool_manager
    
    async def augment(self, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """增强上下文"""
        if not self.tool_manager:
            return context
        
        # 获取可用工具
        tools = await self.tool_manager.get_tools()
        context["tools"] = tools
        
        return context
