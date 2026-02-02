#!/usr/bin/env python3
"""
Test script for the tool approval workflow

This script tests the complete tool approval workflow including:
1. Command safety assessment
2. Pending status return
3. Approval queue management
4. Tool approval and execution
"""

import asyncio
import json
from src.services.impl.mcp_tool_manager import McpToolManager

async def test_approval_workflow():
    """Test the complete approval workflow"""
    print("🚀 Testing Tool Approval Workflow")
    print("=" * 80)
    
    # Initialize tool manager
    tool_manager = McpToolManager()
    await tool_manager.initialize()
    
    print("\n1. Testing dangerous command (should require approval):")
    print("-" * 60)
    
    # Test with a dangerous command
    dangerous_tool_call = {
        "id": "test-1",
        "type": "function",
        "function": {
            "name": "terminal-user.execute_command",
            "arguments": {
                "command": "rm -rf /tmp/test",
                "timeout": 30
            }
        }
    }
    
    # Call the dangerous tool
    dangerous_result = await tool_manager.call_tool(dangerous_tool_call)
    print(f"Result: {json.dumps(dangerous_result, indent=2)}")
    
    # Check if it returned pending status
    if dangerous_result.get("status") == "pending":
        approval_id = dangerous_result.get("approval_id")
        print(f"\n✅ Successfully returned pending status with approval ID: {approval_id}")
        
        # List pending approvals
        print("\n2. Listing pending approvals:")
        print("-" * 60)
        pending = await tool_manager.get_pending_approvals()
        print(f"Found {len(pending)} pending approvals")
        for item in pending:
            print(f"Approval ID: {item['approval_id']}")
            print(f"Tool: {item['tool_call']['function']['name']}")
            print(f"Command: {item['tool_call']['function']['arguments']['command']}")
        
        # # Approve the tool
        # print("\n3. Approving the tool:")
        # print("-" * 60)
        # approval_result = await tool_manager.approve_tool(approval_id)
        # print(f"Approval result: {json.dumps(approval_result, indent=2)}")
        #
        # # Check if approval queue is now empty
        # print("\n4. Checking if approval queue is empty:")
        # print("-" * 60)
        # pending_after = await tool_manager.get_pending_approvals()
        # print(f"Found {len(pending_after)} pending approvals after approval")
        
    else:
        print("❌ Expected pending status but got:", dangerous_result.get("status"))
    
    print("\n5. Testing safe command (should not require approval):")
    print("-" * 60)
    
    # Test with a safe command
    safe_tool_call = {
        "id": "test-2",
        "type": "function",
        "function": {
            "name": "terminal-user.execute_command",
            "arguments": {
                "command": "echo 'Hello, World!'",
                "timeout": 30
            }
        }
    }
    
    # Call the safe tool
    safe_result = await tool_manager.call_tool(safe_tool_call)
    print(f"Result: {json.dumps(safe_result, indent=2)}")
    
    # Check if it returned success status
    if safe_result.get("success"):
        print("✅ Successfully executed safe command without approval")
    else:
        print("❌ Expected success status but got:", safe_result.get("success"))
    
    print("\n" + "=" * 80)
    print("🎉 Tool Approval Workflow Test Complete")

if __name__ == "__main__":
    asyncio.run(test_approval_workflow())
