"""
LLM客户端，用于与各种大语言模型服务进行交互
"""

import httpx
import json
from typing import List, Dict, Any, Optional

import global_statics
from global_statics import logger


class LLMClient:
    """LLM客户端，支持基本的聊天完成请求"""
    
    def __init__(self, backbone_llm_config=None):
        """
        初始化LLM客户端
        
        Args:
            backbone_llm_config: Backbone LLM配置，如果为None则使用config中的配置
        """
        if backbone_llm_config is None:
            backbone_llm_config = global_statics.backbone_llm_config
            
        self.config = backbone_llm_config
        self.base_url = backbone_llm_config.openapi_url
        self.timeout = backbone_llm_config.timeout
        self.session = httpx.AsyncClient(timeout=self.timeout)
        self.api_key = backbone_llm_config.openapi_key
        self.model_name = backbone_llm_config.model_name
        
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
                temperature = self.config.temperature
            if max_tokens is None:
                max_tokens = self.config.max_tokens
                
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                **kwargs
            }
            
            if max_tokens:
                payload["max_tokens"] = max_tokens
                
            if tools:
                payload["tools"] = tools
                
            if tool_choice:
                payload["tool_choice"] = tool_choice
            
            logger.info(f"发送聊天请求，模型: {model}, 消息数: {len(messages)}")
            
            response = await self._make_request(payload)
            
            logger.info(f"收到响应，使用token: {response.get('usage', {})}")
            return response
            
        except Exception as e:
            logger.error(f"聊天请求失败: {str(e)}")
            raise
    
    async def _make_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送HTTP请求到LLM服务
        
        Args:
            payload: 请求负载
            
        Returns:
            响应数据
        """
        url = f"{self.base_url}/v1/chat/completions"
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # 如果有API密钥，添加到请求头
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        try:
            logger.debug(f"请求URL: {url}")
            logger.debug(f"请求负载: {json.dumps(payload, ensure_ascii=False, indent=2)}")
            
            response = await self.session.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            logger.debug(f"响应数据: {json.dumps(result, ensure_ascii=False, indent=2)[:500]}...")
            
            return result
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP错误 {e.response.status_code}: {e.response.text}")
            raise Exception(f"LLM服务返回错误: {e.response.status_code}")
            
        except httpx.RequestError as e:
            logger.error(f"请求错误: {str(e)}")
            raise Exception(f"无法连接到LLM服务: {str(e)}")
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析错误: {str(e)}")
            raise Exception(f"LLM服务返回格式错误: {str(e)}")
    
    def sync_chat_completion(self, *args, **kwargs) -> Dict[str, Any]:
        """
        同步版本的聊天完成请求
        
        Args:
            *args, **kwargs: 与chat_completion相同的参数
            
        Returns:
            响应数据字典
        """
        import asyncio
        return asyncio.run(self.chat_completion(*args, **kwargs))
    
    async def close(self):
        """关闭客户端连接"""
        await self.session.aclose()
        logger.info("LLMClient连接已关闭")
    
    def __del__(self):
        """析构函数，尝试关闭连接"""
        try:
            if hasattr(self, 'session') and self.session:
                logger.debug("LLMClient实例销毁")
        except Exception:
            pass


# 创建默认客户端实例
def create_llm_client(backbone_config=None) -> LLMClient:
    """
    创建LLM客户端实例
    
    Args:
        backbone_config: Backbone配置，如果为None则使用dataModel中的配置
        
    Returns:
        LLMClient实例
    """
    return LLMClient(backbone_config=backbone_config)