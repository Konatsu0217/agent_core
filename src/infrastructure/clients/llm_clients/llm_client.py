"""
LLM客户端，用于与各种大语言模型服务进行交互
基于 OpenAI 官方客户端封装
"""
import asyncio
import json
import uuid

import aiohttp
from openai import AsyncOpenAI
from typing import List, Dict, Any, Optional, AsyncGenerator

import global_statics
from global_statics import logger
from src.infrastructure.clients.llm_clients.abs_llm_client import AbsLLMClient


class OpenAIStyleLLMClient(AbsLLMClient):
    """LLM客户端，支持基本的聊天完成请求"""

    @property
    def provider(self) -> str:
        return self.config.get('provider', 'openai')


    def __init__(self, client_key, backbone_llm_config=None):
        """
        初始化LLM客户端

        Args:
            client_key: 客户端唯一标识，用于区分不同的客户端实例
            backbone_llm_config: Backbone LLM配置，如果为None则使用config中的配置
        """
        if backbone_llm_config is None:
            backbone_llm_config = global_statics.backbone_llm_config

        super().__init__(client_key, backbone_llm_config)

        self.client_key = client_key
        self.config = backbone_llm_config
        self.base_url = backbone_llm_config['openapi_url']
        self.api_key = backbone_llm_config['openapi_key']
        self.model_name = backbone_llm_config['model_name']
        self.timeout = backbone_llm_config.get('timeout', 30)

        # 初始化 OpenAI 客户端
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout
        )

        logger.info(f"LLMClient初始化完成，使用模型: {self.model_name}, base_url: {self.base_url}")

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        发送聊天完成请求

        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "你好"}]
            model: 使用的模型名称，如果为None则使用配置中的模型
            temperature: 温度参数，控制随机性，如果为None则使用配置中的温度
            max_tokens: 最大token数
            tools: 工具定义列表
            tool_choice: 工具选择策略
            **kwargs: 其他参数

        Returns:
            响应数据字典
        """
        try:
            # 使用配置中的默认值
            if model is None:
                model = self.model_name
            if temperature is None:
                temperature = self.config['temperature']
            if max_tokens is None:
                max_tokens = self.config.get('max_tokens')

            # 构建请求参数
            request_params = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                **kwargs
            }

            if max_tokens:
                request_params["max_tokens"] = max_tokens

            if tools:
                request_params["tools"] = tools

            if tool_choice:
                request_params["tool_choice"] = tool_choice

            logger.info(f"发送聊天请求，模型: {model}, 消息数: {len(messages)}")

            # 使用 OpenAI 客户端发送请求
            response = await self.client.chat.completions.create(**request_params)

            # 将响应转换为字典格式
            result = response.model_dump()

            logger.info(f"收到响应，使用token: {result.get('usage', {})}")
            return result

        except Exception as e:
            logger.error(f"聊天请求失败: {str(e)}")
            raise

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[str, Any]:
        try:
            # 使用配置中的默认值
            if model is None:
                model = self.model_name
            if temperature is None:
                temperature = self.config['temperature']
            if max_tokens is None:
                max_tokens = self.config.get('max_tokens')

            # 构建请求参数
            request_params = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "stream": True,
                **kwargs
            }

            if max_tokens:
                request_params["max_tokens"] = max_tokens

            if tools:
                request_params["tools"] = tools

            if tool_choice:
                request_params["tool_choice"] = tool_choice

            logger.info(f"发送聊天请求，模型: {model}, 消息数: {len(messages)}")

            # AsyncOpenAI 流式生成
            stream = await self.client.chat.completions.create(
                **request_params,
            )

            async for chunk in stream:
                yield chunk.model_dump_json()

        except Exception as e:
            logger.error(f"流式聊天请求失败: {e}")
            raise

    async def close(self):
        """关闭客户端连接"""
        await self.client.close()
        logger.info("LLMClient连接已关闭")

    def __del__(self):
        try:
            if hasattr(self, 'client') and self.client:
                logger.debug("LLMClient实例销毁")
        except Exception:
            pass
