from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional

from src.context.manager import get_context_manager
from src.infrastructure.utils.connet_manager import get_ws_manager
from src.infrastructure.utils.pipe import ProcessPipe
from src.infrastructure.logging.logger import get_logger

logger = get_logger()


class RuntimeSession:
    def __init__(self, session_id: str, plugin_config: Dict[str, Any] = None, agent_id: Optional[str] = None, avatar_url: Optional[str] = None):
        self.session_id = session_id
        self.agent_id = agent_id
        self.avatar_url = avatar_url
        self.ws = get_ws_manager()
        self.created_at = datetime.now()

        self.pipe: Optional[ProcessPipe] = None

        # 会话的配置
        self.RuntimeSessionConfig = plugin_config

        # 事件总线
        self.event_bus = EventBus()

        # 缓冲区
        self.buffer = []
        self.sendBuffer = []
        logger.info(f"runtime_session_created session_id={session_id}")

    def createPipe(self) -> ProcessPipe:
        self.pipe = ProcessPipe()
        return self.pipe

    def release(self):
        logger.info(f"runtime_session_release session_id={self.session_id}")
        self.event_bus.unsubscribe_all()
        self.buffer = []
        if self.pipe:
            self.pipe.close()
            self.pipe = None

    def delete(self):
        """删除会话，完全删除不可复原"""
        logger.info(f"runtime_session_delete session_id={self.session_id}")
        get_context_manager().clear_session(self.session_id)
        self.release()


class EventBus:
    def __init__(self):
        self.subscribers = {}

    def subscribe(self, event_type: str, callback):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)

    def publish(self, event_type: str, event_data: Dict[str, Any]):
        if event_type in self.subscribers:
            for callback in self.subscribers[event_type]:
                callback(event_data)

    def unsubscribe(self, event_type: str, callback):
        if event_type in self.subscribers:
            self.subscribers[event_type].remove(callback)

    def unsubscribe_all(self):
        self.subscribers.clear()
