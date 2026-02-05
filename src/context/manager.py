import re
import threading
from copy import deepcopy
from datetime import datetime
from typing import Dict, List, Optional, Any

from src.context.context import Context
from src.context.storage.in_memory import InMemoryStorage
from src.context.storage.sqlite_storage import SQLiteStorage


class ContextManager:
    def __init__(self, storage_backend=None):
        self.storage = storage_backend or InMemoryStorage()
        self._history: Dict[str, List[Context]] = {}
        self._locks: Dict[str, threading.Lock] = {}
        self._pre_snapshot_hooks: List = []
        self._post_snapshot_hooks: List = []

    def _key(self, session_id: str, agent_id: str) -> str:
        return f"{session_id}:{agent_id}"

    def _get_lock(self, key: str) -> threading.Lock:
        if key not in self._locks:
            self._locks[key] = threading.Lock()
        return self._locks[key]

    def create_context(self, session_id: str, agent_id: str, **kwargs) -> Context:
        ctx = Context(session_id=session_id, agent_id=agent_id, **kwargs)
        self._record(ctx)
        return ctx

    def snapshot(self, ctx: Context, note: Optional[str] = None) -> Context:
        key = self._key(ctx.session_id, ctx.agent_id)
        lock = self._get_lock(key)
        with lock:
            for fn in self._pre_snapshot_hooks:
                try:
                    fn(ctx)
                except Exception:
                    pass
            ctx.version += 1
            ctx.updated_at = datetime.now()
            if note:
                ctx.extra.setdefault("notes", []).append({"version": ctx.version, "note": note})
            self._record(ctx)
            for fn in self._post_snapshot_hooks:
                try:
                    fn(ctx)
                except Exception:
                    pass
        return ctx

    def append_message(self, ctx: Context, message: Dict[str, Any], auto_snapshot: bool = True) -> Context:
        ctx.messages = ctx.messages + [message]
        return self.snapshot(ctx) if auto_snapshot else ctx

    def get_history(self, session_id: str, agent_id: str) -> Optional[List[Context]]:
        if session_id in self._history:
            return self._history.get(self._key(session_id, agent_id), [])
        else:
            try:
                key = self._key(session_id, agent_id)
                ctx = self.storage.load(key=key)
                if ctx:
                    self._history.setdefault(key, []).append(ctx)
                return self._history[key]
            except Exception:
                return None


    def get_latest(self, session_id: str, agent_id: str) -> Optional[Context]:
        hist = self.get_history(session_id, agent_id)
        return hist[-1] if hist else None

    def delete_history(self, session_id: str, agent_id: str) -> int:
        key = self._key(session_id, agent_id)
        lock = self._get_lock(key)
        with lock:
            self._history.pop(key, None)
            if hasattr(self.storage, "delete_by_key"):
                return self.storage.delete_by_key(key)
        return 0

    def clear_session(self, session_id: str) -> int:
        prefix = f"{session_id}:"
        keys_to_delete = [k for k in self._history.keys() if k.startswith(prefix)]
        for key in keys_to_delete:
            self._history.pop(key, None)
        if hasattr(self.storage, "delete_by_prefix"):
            return self.storage.delete_by_prefix(prefix)
        return 0

    def delete_versions(
        self,
        session_id: str,
        agent_id: str,
        min_version: Optional[int] = None,
        max_version: Optional[int] = None,
    ) -> int:
        key = self._key(session_id, agent_id)
        lock = self._get_lock(key)
        with lock:
            hist = self._history.get(key, [])
            if hist:
                self._history[key] = [
                    c
                    for c in hist
                    if not (
                        (min_version is None or c.version >= min_version)
                        and (max_version is None or c.version <= max_version)
                    )
                ]
            if hasattr(self.storage, "delete_by_version_range"):
                return self.storage.delete_by_version_range(key, min_version, max_version)
        return 0

    def rollback(self, session_id: str, agent_id: str, version: int) -> Optional[Context]:
        key = self._key(session_id, agent_id)
        hist = self.get_history(session_id, agent_id)
        if not hist:
            return None
        target = None
        for c in reversed(hist):
            if c.version == version:
                target = c
                break
        if target is None:
            return None
        lock = self._get_lock(key)
        with lock:
            latest_version = hist[-1].version
            clone = deepcopy(target)
            clone.version = latest_version + 1
            clone.updated_at = datetime.now()
            clone.extra.setdefault("notes", []).append({"version": clone.version, "note": "rollback"})
            self._record(clone)
        return clone

    def _record(self, ctx: Context):
        key = self._key(ctx.session_id, ctx.agent_id)
        snap = deepcopy(ctx)
        self._history.setdefault(key, []).append(snap)
        self.storage.save(key, ctx)

    def register_pre_snapshot_hook(self, fn):
        self._pre_snapshot_hooks.append(fn)

    def register_post_snapshot_hook(self, fn):
        self._post_snapshot_hooks.append(fn)

_manager = ContextManager(SQLiteStorage())
_manager.register_post_snapshot_hook(
    lambda ctx: print(f"Made a Snapshot of Context, estimated token: {(ctx.messages.__sizeof__() + ctx.system_prompt.__sizeof__() + ctx.tools.__sizeof__() + ctx.tools.__sizeof__())/3.5}")
)

def get_context_manager() -> ContextManager:
    return _manager
