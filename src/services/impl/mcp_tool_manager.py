from typing import List, Dict, Any, Optional
from src.services.interfaces.tool_manager import IToolManager
from src.infrastructure.clients.mcp_client import MCPHubClient
from global_statics import global_config
import asyncio
import uuid


class McpToolManager(IToolManager):
    """基于 MCP 的工具管理器"""
    
    def __init__(self):
        self.mcpClient = MCPHubClient(base_url=f"{global_config['mcphub_url']}:{global_config['mcphub_port']}")
        self.tool_cache: List[Dict[str, Any]] = []
        self.approval_queue: Dict[str, Dict[str, Any]] = {}  # 审批队列
        self.approval_results: Dict[str, Dict[str, Any]] = {}  # 审批结果
    
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
        function = tool_call.get("function", {})
        tool_name = function.get("name", "")
        arguments = function.get("arguments", {})
        
        # 调用工具
        result = await self.mcpClient.call_tool(
            tool=tool_name,
            arguments=arguments
        )
        
        # 处理pending状态
        if result.get("status") == "pending":
            approval_id = str(uuid.uuid4())
            # 添加到审批队列
            self.approval_queue[approval_id] = {
                "tool_call": tool_call,
                "pending_data": result.get("data", {}),
                "timestamp": asyncio.get_event_loop().time()
            }
            # 返回pending状态和审批ID
            return {
                "success": False,
                "status": "pending",
                "approval_id": approval_id,
                "message": "Tool execution requires approval",
                "data": result.get("data", {})
            }
        
        return result
    
    async def get_pending_approvals(self) -> List[Dict[str, Any]]:
        """获取待审批的工具调用"""
        return [
            {
                "approval_id": approval_id,
                "tool_call": item["tool_call"],
                "pending_data": item["pending_data"],
                "timestamp": item["timestamp"]
            }
            for approval_id, item in self.approval_queue.items()
        ]
    
    async def approve_tool(self, approval_id: str) -> Dict[str, Any]:
        """批准工具执行"""
        if approval_id not in self.approval_queue:
            return {
                "success": False,
                "error": "Approval ID not found"
            }
        
        item = self.approval_queue[approval_id]
        tool_call = item["tool_call"]
        function = tool_call.get("function", {})
        tool_name = function.get("name", "")
        arguments = function.get("arguments", {})
        
        # 调用批准方法
        result = await self.mcpClient.approve_tool(
            tool=tool_name,
            arguments=arguments,
            approval_id=approval_id
        )
        
        # 从审批队列中移除
        del self.approval_queue[approval_id]
        # 保存审批结果
        self.approval_results[approval_id] = result
        
        return result
    
    async def reject_tool(self, approval_id: str) -> Dict[str, Any]:
        """拒绝工具执行"""
        if approval_id not in self.approval_queue:
            return {
                "success": False,
                "error": "Approval ID not found"
            }
        
        # 从审批队列中移除
        del self.approval_queue[approval_id]
        # 保存拒绝结果
        self.approval_results[approval_id] = {
            "success": False,
            "status": "rejected",
            "message": "Tool execution rejected"
        }
        
        return {
            "success": True,
            "status": "rejected",
            "message": "Tool execution rejected"
        }
    
    async def get_approval_result(self, approval_id: str) -> Optional[Dict[str, Any]]:
        """获取审批结果"""
        return self.approval_results.get(approval_id)
    
    async def clear_approval_history(self):
        """清除审批历史"""
        self.approval_results.clear()
        return {"success": True, "message": "Approval history cleared"}
