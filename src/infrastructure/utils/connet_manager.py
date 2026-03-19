import json
import logging
from typing import List, Dict, Optional, Set

from starlette.websockets import WebSocket

from src.domain.events import EventEnvelope

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self):
        self.cache: Dict[str, WebSocket] = {}
        # 广播会话 ID 集合：这些 session 的事件会广播到所有客户端
        self._broadcast_sessions: Set[str] = set()

    async def get_websocket(self, session_id: str) -> Optional[WebSocket]:
        return self.cache.get(session_id)

    async def cache_websocket(self, session_id: str, websocket: WebSocket):
        self.cache[session_id] = websocket
        logger.info(f"ws_connected session_id={session_id} total={len(self.cache)}")

    async def uncache_websocket(self, session_id: str):
        if session_id in self.cache:
            del self.cache[session_id]
        logger.info(f"ws_disconnected session_id={session_id} total={len(self.cache)}")

    def register_broadcast_session(self, session_id: str):
        """注册一个广播会话 — 该会话的事件会发送给所有客户端"""
        self._broadcast_sessions.add(session_id)
        logger.info(f"broadcast_session_registered session_id={session_id}")

    def is_broadcast_session(self, session_id: str) -> bool:
        """判断是否为广播会话"""
        return session_id in self._broadcast_sessions

    async def broadcast_json(self, data: dict):
        """向所有连接的 WebSocket 客户端广播 JSON 消息"""
        if not self.cache:
            return

        disconnected = []
        for sid, ws in self.cache.items():
            try:
                await ws.send_json(data)
            except Exception as e:
                logger.warning(f"broadcast_send_failed session_id={sid} error={e}")
                disconnected.append(sid)

        for sid in disconnected:
            self.cache.pop(sid, None)

        if disconnected:
            logger.info(f"broadcast_cleanup removed={len(disconnected)} remaining={len(self.cache)}")

    async def broadcast_websocket(self, msg: str, websocket: WebSocket):
        """向所有连接的 WebSocket 客户端广播文本消息（兼容旧接口）"""
        if not self.cache:
            return
        disconnected = []
        for session_id, ws in self.cache.items():
            try:
                await ws.send_text(msg)
            except Exception as e:
                logger.warning(f"broadcast_text_failed session_id={session_id} error={e}")
                disconnected.append(session_id)
        for sid in disconnected:
            self.cache.pop(sid, None)

    async def send_event_to(self, session_id: str, msg: EventEnvelope):
        """发送事件到指定会话 — 如果是广播会话则广播到所有客户端"""
        if self.is_broadcast_session(session_id):
            await self.broadcast_json(msg)
            return

        websocket = self.cache.get(session_id)
        if websocket:
            await websocket.send_json(msg)


_ws_manager = WebSocketManager()

def get_ws_manager() -> WebSocketManager:
    return _ws_manager
