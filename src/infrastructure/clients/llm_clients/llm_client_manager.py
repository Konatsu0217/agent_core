import uuid
from typing import Dict

import global_statics
from src.infrastructure.clients.llm_clients.abs_llm_client import AbsLLMClient
from src.infrastructure.clients.llm_clients.llm_client import OpenAIStyleLLMClient


# from src.infrastructure.clients.llm_clients.llm_client import OllamaLLMClient


class LLMClientManager:
    """LLM客户端管理器，管理多个LLM客户端实例"""

    def __init__(self):
        self.clientMap: Dict[str, AbsLLMClient] = {}
        # client会有更多的属性，其实这里的一个client在我的计划里类似于一个agent
        # 通过uuid来区分不同agent，有独立的context, pe, rag, tool等等，比如说 视觉模型 --> 视觉client，后续再说

    def get_client(self, name: str=None, config=None) -> AbsLLMClient:
        if config is None:
            config = global_statics.backbone_llm_config

        client_key = f"{name}_{config['model_name']}_{uuid.uuid1()}"

        provider = config.get("provider")

        if client_key not in self.clientMap:
            self.clientMap[client_key] = OpenAIStyleLLMClient(client_key, config)
            # if provider == "siliconflow":
            #     self.clientMap[client_key] = OpenAIStyleLLMClient(client_key, config)
            # elif provider == "ollama":
            #     self.clientMap[client_key] = AbsLLMClient(client_key, config)
            # else :
            #     raise NotImplementedError(f"不支持的LLM供应商: {provider}")

        return self.clientMap[client_key]

    async def close_all(self):
        """关闭所有客户端连接"""
        for client in self.clientMap.values():
            await client.close()
        self.clientMap.clear()
        global_statics.logger.info("所有LLMClient连接已关闭")


static_llmClientManager = LLMClientManager()
