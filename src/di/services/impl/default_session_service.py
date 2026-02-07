from typing import Dict, Any

from typing_extensions import deprecated

from src.di.services.interfaces.session_service import ISessionService
from src.infrastructure.clients.session_manager import get_session_manager
from src.infrastructure.logging.logger import get_logger

logger = get_logger()


@deprecated("DefaultSessionService is deprecated, please use SessionManager instead")
class DefaultSessionService(ISessionService):
    """默认会话服务"""

    def __init__(self):
        self.session_manager = get_session_manager()

    async def get_session(self, session_id: str, agent_id: str) -> Dict[str, Any]:
        """获取会话信息"""
        try:
            return await self.session_manager.get_session(session_id, agent_id)
        except Exception as e:
            logger.warning(f"⚠️ SessionManager get_session failed: {e}")
            return {}

    async def update_context(self, session_id: str, messages: list[dict[str, str]]) -> None:
        """更新会话上下文"""
        try:
            await self.session_manager.update_context(session_id, messages)
        except Exception as e:
            logger.warning(f"⚠️ SessionManager update_context failed: {e}")
