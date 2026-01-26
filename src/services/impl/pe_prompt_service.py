from typing import Dict, Any
import uuid
from src.services.interfaces.prompt_service import IPromptService
from src.infrastructure.clients.pe_client import PEClient
from global_statics import global_config


class PePromptService(IPromptService):
    """基于 PE 的提示词服务"""
    
    def __init__(self):
        self.peClient = PEClient(global_config['pe_url'])
    
    async def initialize(self):
        """初始化提示词服务"""
        try:
            await self.peClient.connect()
            print("✅ PE客户端连接已建立")
        except Exception as e:
            print(f"❌ PE客户端连接失败: {e}")
    
    async def build_prompt(self, session_id: str, user_query: str, **kwargs) -> Dict[str, Any]:
        """构建提示词"""
        return await self.peClient.build_prompt(
            session_id=session_id,
            user_query=user_query,
            request_id=str(uuid.uuid4()),
            stream=False
        )
