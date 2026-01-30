import hashlib
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
        # 通过配置的特征值来区分不同的客户端实例

    def _generate_client_key(self, name: str=None, config=None) -> str:
        """根据配置生成唯一的客户端密钥"""
        # 使用配置的关键参数生成哈希值
        config_str = f"{config.get('openapi_url', '')}_{config.get('model_name', '')}_{config.get('temperature', '')}_{config.get('max_tokens', '')}"
        config_hash = hashlib.md5(config_str.encode()).hexdigest()
        return f"{name or 'default'}_{config_hash}"

    def get_client(self, name: str=None, config=None) -> AbsLLMClient:
        """
        获取或创建LLM客户端实例
        
        Args:
            name: 客户端名称，用于标识不同的客户端
            config: LLM配置，如果为None则使用全局配置
            
        Returns:
            LLM客户端实例
        """
        if config is None:
            config = global_statics.backbone_llm_config

        client_key = self._generate_client_key(name, config)

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
