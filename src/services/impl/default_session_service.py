from typing import Dict, Any
from src.services.interfaces.session_service import ISessionService
from src.infrastructure.clients.session_manager import get_session_manager


class DefaultSessionService(ISessionService):
    """默认会话服务"""
    
    def __init__(self):
        self.session_manager = get_session_manager()
    
    async def get_session(self, session_id: str, agent_name: str) -> Dict[str, Any]:
        """获取会话信息"""
        try:
            return await self.session_manager.get_session(session_id, agent_name)
        except Exception as e:
            print(f"⚠️ SessionManager get_session failed: {e}")
            return {}
