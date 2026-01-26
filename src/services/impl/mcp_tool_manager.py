from typing import List, Dict, Any
from src.services.interfaces.tool_manager import IToolManager
from src.infrastructure.clients.mcp_client import MCPHubClient
from global_statics import global_config


class McpToolManager(IToolManager):
    """基于 MCP 的工具管理器"""
    
    def __init__(self):
        self.mcpClient = MCPHubClient(base_url=f"{global_config['mcphub_url']}:{global_config['mcphub_port']}")
        self.tool_cache: List[Dict[str, Any]] = []
    
    async def initialize(self):
        """初始化工具管理器"""
        try:
            tools = await self.mcpClient.get_tools()
            self.tool_cache = tools
            print(f"✅ MCPHubClient 发现 {len(tools)} 个工具")
        except Exception as e:
            print(f"⚠️ MCPHubClient get_tools failed: {e}")
            self.tool_cache = []
    
    async def get_tools(self) -> List[Dict[str, Any]]:
        """获取可用工具列表"""
        if not self.tool_cache:
            await self.initialize()
        return self.tool_cache
    
    async def call_tool(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """调用工具"""
        return await self.mcpClient.call_tool(
            id=tool_call["id"],
            type=tool_call["type"],
            function=tool_call["function"],
        )
