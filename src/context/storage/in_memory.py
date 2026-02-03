from typing import Dict, Optional
from src.context.context import Context


class InMemoryStorage:
    def __init__(self):
        self._store: Dict[str, Dict[int, Context]] = {}
        self._latest: Dict[str, int] = {}

    def save(self, key: str, context: Context):
        versions = self._store.setdefault(key, {})
        versions[context.version] = context
        self._latest[key] = context.version

    def load(self, key: str, version: Optional[int] = None) -> Optional[Context]:
        if version is None:
            version = self._latest.get(key)
        return self._store.get(key, {}).get(version)

    def load_all(self) -> Dict[str, Dict[int, Context]]:
        return self._store
