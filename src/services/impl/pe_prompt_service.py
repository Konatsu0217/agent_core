from typing import Dict, Any, Optional
import uuid
from src.services.interfaces.prompt_service import IPromptService
from src.infrastructure.clients.pe_client import PEClient
from global_statics import global_config
from tools.prompt_server import PromptBaker


class PePromptService(IPromptService):
    """基于 PE 的提示词服务"""
    
    def __init__(self):
        self.pe_baker: Optional[PromptBaker] = PromptBaker()
    
    async def initialize(self):
        """初始化提示词服务"""
        try:
            self.pe_baker = PromptBaker()
            print("✅ PE_Baker实例初始化完毕")
        except Exception as e:
            print(f"❌ PE_Baker实例初始化失败 {e}")
    
    async def build_prompt(self, session_id: str, agent_profile:Dict[str,Any], **kwargs) -> Dict[str, Any]:
        """构建提示词"""
        return await self.pe_baker.bake_system_prompt(
            session_id=session_id,
            agent_profile=agent_profile
        )
