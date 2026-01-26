from abc import ABC, abstractmethod
from typing import List, Dict, Any, AsyncGenerator


class AbsLLMClient(ABC):
    """
    抽象 LLM Client
    任何 LLM 供应商都必须实现此接口
    """

    def __init__(self, client_key: str, config: Dict[str, Any]):
        self.client_key = client_key
        self.config = config
        self.model_name = config.get("model_name")

    # ========= 核心能力 =========

    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """一次性生成"""
        pass

    @abstractmethod
    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> AsyncGenerator[Any, None]:
        """流式生成"""
        pass

    # ========= 生命周期 =========

    @abstractmethod
    async def close(self):
        pass

    # ========= 元信息（用于能力判断） =========

    @property
    @abstractmethod
    def provider(self) -> str:
        """openai / ollama / deepseek / custom"""
        pass

    @property
    def supports_tools(self) -> bool:
        return False

    @property
    def supports_vision(self) -> bool:
        return False
