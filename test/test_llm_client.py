import asyncio

from src.infrastructure.clients.llm_clients.llm_client import LLMClientManager


if __name__ == "__main__":
    llmClientManager = LLMClientManager()
    backBoneLLMClient = llmClientManager.get_client()

    response = asyncio.run(
        backBoneLLMClient.chat_completion(
        messages=[
            {"role": "user", "content": "你好"}
        ]
    ))
    print(response)