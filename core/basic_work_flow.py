import asyncio
import time

from clients.llm_client import LLMClientManager
from clients.mcp_client import MCPHubClient
from clients.pe_client import PEClient
from global_statics import global_config

async def async_get_pe_and_mcp_tools(peClient: PEClient, mcpClient: MCPHubClient):
    # ✅ 统一创建 Task 对象
    pe_task = asyncio.create_task(peClient.build_prompt(
        session_id="test_session_001",
        user_query="你好，请帮我执行这一段python程序print('hello world')",
        request_id="test_request_001",
        stream=False
    ))

    mcp_task = asyncio.create_task(mcpClient.get_tools())

    # 并行执行
    try:
        results = await asyncio.wait_for(
            asyncio.gather(pe_task, mcp_task, return_exceptions=True),
            timeout=5
        )

        llm_request_response, tools = results

        # ✅ 处理异常
        if isinstance(llm_request_response, Exception):
            print(f"❌ PE build_prompt failed: {llm_request_response}")
            return

        if isinstance(tools, Exception):
            print(f"⚠️ MCPHubClient get_tools failed: {tools}")
            tools = []

        # ✅ 正确提取数据
        llm_request = llm_request_response.get('llm_request', {})
        messages = llm_request.get('messages', [])

        print(f"✅ PE build_prompt messages: {messages}")
        print(f"✅ Available tools: {tools}")
        return messages, tools

    except asyncio.TimeoutError:
        print("❌ Timeout: PE or MCP request took too long")
        return [], []
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return [], []

async def main():
    print("\n" + "=" * 50)
    print("Stage 1: 初始化")
    llmClientManager = LLMClientManager()
    backBoneLLMClient = llmClientManager.get_client()
    
    # 初始化PE客户端并建立连接
    peClient = PEClient(global_config['pe_url'])
    try:
        await peClient.connect()
        print("✅ PE客户端连接已建立")
    except Exception as e:
        print(f"❌ PE客户端连接失败: {e}")
        return

    # 初始化mcp管理中心客户端
    mcpClient = MCPHubClient(global_config['mcphub_url'])

    
    print("\n" + "=" * 50)
    print("Stage 2: PE + MCP工具发现")
    messages, tools = await async_get_pe_and_mcp_tools(peClient, mcpClient)
    
    print("\n" + "=" * 50)
    print("Stage 3: 调用llm，获得llm_response")
    print(f"非流式 client_key: {backBoneLLMClient.client_key}")
    response = await backBoneLLMClient.chat_completion(
        messages=messages,
        tools=tools
    )

    print("\n" + "=" * 50)
    print("Stage 4: llm_response输出")
    print(response)


    # print("\n" + "=" * 50)
    # print(f"流式 client_key: {backBoneLLMClient.client_key}")
    # start_time = time.time()
    # async for delta in backBoneLLMClient.chat_completion_stream(
    #     messages=ready.get('messages', []),
    #     tools=ready.get('tools', [])
    # ):
    #     if(start_time != 0):
    #         end_time = time.time()
    #         print(f"首token耗时: {end_time - start_time} 秒")
    #         start_time = 0
    #     print(delta, end='\n')
    
    # 关闭PE客户端连接
    await peClient.close()

if __name__ == "__main__":
    asyncio.run(main())