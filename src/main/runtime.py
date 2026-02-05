from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any

from src.context.manager import get_context_manager
from src.infrastructure.utils.connet_manager import get_ws_manager
from src.infrastructure.utils.pipe import ProcessPipe


class RuntimeSession:
    def __init__(self, session_id: str, plugin_config: Dict[str, Any] = None):
        self.session_id = session_id
        self.ws = get_ws_manager()
        self.created_at = datetime.now()

        self.pipe = ProcessPipe()

        # 会话的配置
        self.RuntimeSessionConfig = plugin_config

        # 事件总线
        self.event_bus = EventBus()

        # 缓冲区
        self.buffer = []

    def createPipe(self) -> ProcessPipe:
        return self.pipe

    def release(self):
        self.event_bus.unsubscribe_all()
        self.buffer = []
        self.pipe.close()

    def delete(self):
        """删除会话，完全删除不可复原"""
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
