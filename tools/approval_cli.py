#!/usr/bin/env python3
"""
Tool Approval CLI

This script provides a simple interface to manage pending tool approvals.
"""

import asyncio
import json
from src.services.impl.mcp_tool_manager import McpToolManager

async def main():
    """Main function for the approval CLI"""
    print("🚀 Tool Approval CLI")
    print("=" * 50)
    
    # Initialize tool manager
    tool_manager = McpToolManager()
    await tool_manager.initialize()
    
    while True:
        print("\nOptions:")
        print("1. List pending approvals")
        print("2. Approve a tool")
        print("3. Reject a tool")
        print("4. Exit")
        
        choice = input("Enter your choice (1-4): ")
        
        if choice == "1":
            # List pending approvals
            pending = await tool_manager.get_pending_approvals()
            print(f"\n📋 Found {len(pending)} pending approvals:")
            print("-" * 80)
            
            if not pending:
                print("No pending approvals found.")
            else:
                for i, item in enumerate(pending, 1):
                    approval_id = item["approval_id"]
                    tool_call = item["tool_call"]
                    pending_data = item["pending_data"]
                    timestamp = item["timestamp"]
                    
                    print(f"\n{i}. Approval ID: {approval_id}")
                    print(f"   Tool: {tool_call.get('function', {}).get('name', 'Unknown')}")
                    print(f"   Arguments: {json.dumps(tool_call.get('function', {}).get('arguments', {}), indent=2)}")
                    print(f"   Status: {pending_data.get('status', 'Unknown')}")
                    print(f"   Message: {pending_data.get('message', 'No message')}")
                    print(f"   Safety Assessment: {json.dumps(pending_data.get('safety_assessment', {}), indent=2)}")
            print("-" * 80)
            
        elif choice == "2":
            # Approve a tool
            approval_id = input("Enter approval ID to approve: ")
            result = await tool_manager.approve_tool(approval_id)
            print(f"\n✅ Approval result:")
            print(json.dumps(result, indent=2))
            
        elif choice == "3":
            # Reject a tool
            approval_id = input("Enter approval ID to reject: ")
            result = await tool_manager.reject_tool(approval_id)
            print(f"\n❌ Rejection result:")
            print(json.dumps(result, indent=2))
            
        elif choice == "4":
            # Exit
            print("\n👋 Exiting Tool Approval CLI...")
            break
        
        else:
            print("\n❌ Invalid choice. Please try again.")

if __name__ == "__main__":
    asyncio.run(main())
