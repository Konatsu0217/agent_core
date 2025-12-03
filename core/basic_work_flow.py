import asyncio
import json
import websockets
from clients.llm_client import LLMClientManager
from global_statics import global_config


async def test_websocket_build_prompt():
    """
    WebSocket客户端测试：连接build_prompt端点并发送请求
    """
    uri = f"{global_config['pe_url']}/ws/build_prompt"  # 根据实际服务器地址修改

    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket连接已建立")

            # 构建请求消息
            request_data = {
                "type": "build_prompt",
                "request_id": "test_request_001",
                "data": {
                    "session_id": "test_session_001",
                    "user_query": "你好，请帮我执行这一段python程序“print('hello world')”",
                    "stream": False
                }
            }

            # 发送请求
            await websocket.send(json.dumps(request_data))
            print(f"📤 请求已发送: {json.dumps(request_data, ensure_ascii=False, indent=2)}")

            # 接收响应
            response = await websocket.recv()
            response_data = json.loads(response)

            print(f"📥 收到响应: {json.dumps(response_data, ensure_ascii=False, indent=2)}")

            # 检查响应状态
            if response_data.get("status") == "success":
                print("✅ build_prompt请求成功")
                print(f"响应数据: {response_data.get('data', {})}")
                return response_data.get('data', {})
            else:
                print(f"❌ build_prompt请求失败: {response_data.get('error', '未知错误')}")

    except websockets.exceptions.WebSocketException as e:
        print(f"❌ WebSocket连接错误: {e}")
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")


async def main():
    print("\n" + "=" * 50)
    print("Stage 1: 初始化")
    llmClientManager = LLMClientManager()
    backBoneLLMClient = llmClientManager.get_client()
    print("\n" + "=" * 50)
    print("Stage 2: 调用pe，获得完整的llm_request")
    after_pe_response = await test_websocket_build_prompt()
    ready = after_pe_response.get("llm_request")
    print("\n" + "=" * 50)
    print("Stage 3: 调用llm，获得llm_response")
    response = await backBoneLLMClient.chat_completion(
        messages=ready.get('messages', []),
        tools=ready.get('tools', [])
    )
    print("\n" + "=" * 50)
    print("Stage 4: llm_response输出")
    print(response)

if __name__ == "__main__":
    asyncio.run(main())