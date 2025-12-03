import asyncio
from clients.llm_client import LLMClientManager
from clients.pe_client import PEClient
from global_statics import global_config


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
    
    print("\n" + "=" * 50)
    print("Stage 2: 调用pe，获得完整的llm_request")
    try:
        after_pe_response = await peClient.build_prompt(
            session_id="test_session_001",
            user_query="你好，请帮我执行这一段python程序print('hello world')",
            request_id="test_request_001",
            stream=False
        )
        ready = after_pe_response.get("llm_request")
    except Exception as e:
        print(f"❌ PE请求失败: {e}")
        await peClient.close()
        return
    
    print("\n" + "=" * 50)
    print("Stage 3: 调用llm，获得llm_response")

    print("\n" + "=" * 50)
    print(f"client_key: {backBoneLLMClient.client_key}")
    response = await backBoneLLMClient.chat_completion(
        messages=ready.get('messages', []),
        tools=ready.get('tools', [])
    )
    print("\n" + "=" * 50)
    print("Stage 4: llm_response输出")
    print(response)
    
    # 关闭PE客户端连接
    await peClient.close()

if __name__ == "__main__":
    asyncio.run(main())