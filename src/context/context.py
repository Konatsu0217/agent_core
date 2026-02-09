from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime
import json


@dataclass
class Context:
    session_id: str
    agent_id: str
    user_query: str
    messages: List[Dict[str, Any]] = field(default_factory=list) # 持续维护除了prompt以外的所有上下文
    tools: List[Dict[str, Any]] = field(default_factory=list)
    memory: str = field(default_factory=str)
    schedule: str = field(default_factory=str)
    session: Optional[Dict[str, Any]] = None # 暂时没有用了，先占位吧
    session_metadata: Dict[str, Any] = field(default_factory=dict) # 消息发送时间之类的
    system_prompt: Optional[str] = None
    avatar_url: Optional[str] = None
    version: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Context":
        return cls(**data)

    def to_json(self) -> str:
        d = self.to_dict()
        d["created_at"] = self.created_at.isoformat()
        d["updated_at"] = self.updated_at.isoformat()
        return json.dumps(d, ensure_ascii=False)

    @classmethod
    def from_json(cls, data: str) -> "Context":
        obj = json.loads(data)
        if isinstance(obj.get("created_at"), str):
            obj["created_at"] = datetime.fromisoformat(obj["created_at"])
        if isinstance(obj.get("updated_at"), str):
            obj["updated_at"] = datetime.fromisoformat(obj["updated_at"])
        return cls(**obj)
