from typing import Dict, Any, Optional
from src.di.services.interfaces.prompt_service import IPromptService
from tools.prompt_server import PromptBaker
from src.infrastructure.logging.logger import get_logger

logger = get_logger()


class PePromptService(IPromptService):
    """基于 PE 的提示词服务"""
    
    def __init__(self):
        self.pe_baker: Optional[PromptBaker] = PromptBaker()
    
    async def initialize(self):
        """初始化提示词服务"""
        try:
            self.pe_baker = PromptBaker()
            logger.info("PE_Baker实例初始化完毕")
        except Exception as e:
            logger.exception(f"PE_Baker实例初始化失败 {e}")
    
    async def build_prompt(self, session_id: str, agent_profile:Dict[str,Any], **kwargs) -> Dict[str, Any]:
        """构建提示词"""
        return await self.pe_baker.bake_system_prompt(
            session_id=session_id,
            agent_profile=agent_profile
        )
