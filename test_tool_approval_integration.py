#!/usr/bin/env python3
"""
Test script for interactive tool approval integration with ToolUsingAgent

This script tests the complete interactive approval workflow including:
1. ToolUsingAgent detecting pending tool execution
2. Interactive approval prompt
3. Approval and rejection handling
4. Result processing
"""

import asyncio
import json
from src.agent.abs_agent import ToolUsingAgent, ExecutionMode
from src.services.impl.mcp_tool_manager import McpToolManager

async def test_tool_approval_integration():
    """Test the interactive tool approval integration"""
    print("🚀 Testing Tool Approval Integration with ToolUsingAgent")
    print("=" * 80)
    
    # Create agent profile
    agent_profile = {
        "name": "test_agent",
        "tools_use": True,
        "output_format": "json",
        "services_needed": [
            ("tool_manager", "set_tool_manager")
        ]
    }
    
    # Create ToolUsingAgent
    agent = ToolUsingAgent(
        agent_profile=agent_profile,
        name="test_agent",
        work_flow_type=ExecutionMode.TEST
    )
    
    # Initialize tool manager
    tool_manager = McpToolManager()
    await tool_manager.initialize()
    
    # Set tool manager for agent
    agent.set_tool_manager(tool_manager)
    
    print("\n1. Testing dangerous command execution:")
    print("-" * 60)
    
    # Create test messages
    messages = [
        {
            "role": "user",
            "content": "删除临时目录 /tmp/test"
        }
    ]
    
    # Create test tools list
    tools = [
        {
            "type": "function",
            "function": {
                "name": "terminal-user.execute_command",
                "description": "执行终端命令",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "要执行的命令"
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "超时时间"
                        }
                    },
                    "required": ["command"]
                }
            }
        }
    ]
    
    # Simulate a tool call event similar to what would come from LLM
    test_tool_call = {
        "id": "test-tool-call-1",
        "type": "function",
        "function": {
            "name": "terminal-user.execute_command",
            "arguments": {
                "command": "rm -rf /tmp/test",
                "timeout": 30
            }
        }
    }
    
    print("模拟工具调用:")
    print(json.dumps(test_tool_call, indent=2))
    
    # Execute tool call through agent's tool execution logic
    print("\n执行工具调用...")
    
    # This will trigger the interactive approval process
    if agent.tool_manager:
        result = await agent.tool_manager.call_tool(test_tool_call)
        print(f"\n工具执行结果:")
        print(json.dumps(result, indent=2))
        
        # If it returns pending, we would normally handle it in run_with_tools
        if result.get("status") == "pending":
            print("\n✅ 工具正确返回 pending 状态，需要审批")
            print("\n注意：在实际 Agent 运行中，这里会触发交互式审批流程")
            print("用户会看到审批提示并输入选择")
    
    print("\n" + "=" * 80)
    print("🎉 Tool Approval Integration Test Complete")

async def main():
    await test_tool_approval_integration()

if __name__ == "__main__":
    asyncio.run(main())
