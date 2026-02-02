import datetime
from abc import ABC, abstractmethod
import importlib
from typing import Dict, Optional

class AbsAugmenter(ABC):
    def __init__(self, name, **kwargs):
        self.extra_info = None
        self.name = name

    async def augment(self, context, **kwargs):
        context.system_prompt = context.system_prompt + '\n' + self.build_extraInfo()
        return context

    @abstractmethod
    def build_extraInfo(self):
        pass


class TimeAugmenter(AbsAugmenter):
    def __init__(self, **kwargs):
        super().__init__("time_augmenter", **kwargs)

    def build_extraInfo(self):
        return f'当前时间: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'

REGISTRY: Dict[str, type] = {
    "time_augmenter": TimeAugmenter,
}


def resolve_augmenter_class(name: str) -> Optional[type]:
    if name in REGISTRY:
        return REGISTRY[name]
    if "." in name:
        try:
            module_path, cls_name = name.rsplit(".", 1)
            module = importlib.import_module(module_path)
            return getattr(module, cls_name, None)
        except Exception:
            return None
    return None


def create_augmenter(name: str, params: Optional[dict] = None):
    cls = resolve_augmenter_class(name)
    if not cls:
        return None
    params = params or {}
    try:
        return cls(**params)
    except Exception:
        return None
