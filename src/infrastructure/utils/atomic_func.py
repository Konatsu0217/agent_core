from src.infrastructure.clients.llm_clients.llm_client_manager import static_llmClientManager


async def atomic_llm_call(messages, llm_client = None):
    if llm_client is None:
        llm_client = static_llmClientManager.get_client()
    result = await llm_client.call(messages)
    return result["choices"][0]["message"]["content"]
