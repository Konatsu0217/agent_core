from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

class ClientEventType(str, Enum):
    # 会话建立
    INIT_SESSION = "init_session"
    ATTACH_SESSION = "attach_session"
    # 消息过程中
    USER_MESSAGE = "user_message"
    TOOL_APPROVAL = "tool_approval"
    # 标准事件
    HEARTBEAT = "heartbeat"
    DETACH_SESSION = "detach_session"
    DELETE_SESSION = "delete_session"

class ServerEventType(str, Enum):
    # Agent
    AGENT_TEXT_DELTA = "text_delta"
    AGENT_THINK_DELTA = "think_delta"
    AGENT_TOOL_CALL = "tool_call"
    AGENT_TOOL_RESULT = "tool_result"
    AGENT_APPROVAL_REQUIRED = "approval_required"
    AGENT_APPROVAL_DECISION = "approval_decision"
    # 标准事件
    HEARTBEAT = "heartbeat"
    FINAL = "final"
    ERROR = "error"
    USAGE = "usage"
    STATE = "state"
    # TTS


@dataclass
class UserMessagePayload:
    text: str
    session_id: str
    attachments: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ToolApprovalPayload:
    approval_id: str
    session_id: str
    decision: Literal["approved", "rejected"]
    message: Optional[str] = None


@dataclass
class HeartbeatPayload:
    session_id: str
    client_time: float


@dataclass
class InitSessionPayload:
    user_id: str = None
    agent_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    plugin_config: Optional[Dict[str, Any]] = None


@dataclass
class AttachSessionPayload:
    session_id: str
    agent_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class DetachSessionPayload:
    session_id: str
    reason: Optional[str] = None


@dataclass
class DeleteSessionPayload:
    session_id: str
    reason: Optional[str] = None


ClientEventPayload = Union[
    UserMessagePayload,
    ToolApprovalPayload,
    HeartbeatPayload,
    InitSessionPayload,
    AttachSessionPayload,
    DetachSessionPayload,
    DeleteSessionPayload,
]


@dataclass
class TextDeltaPayload:
    text: str


@dataclass
class ThinkDeltaPayload:
    text: str


@dataclass
class ToolCallPayload:
    name: str
    arguments: Any


@dataclass
class ToolResultPayload:
    name: str
    success: bool
    result: Any


@dataclass
class ApprovalRequiredPayload:
    approval_id: str
    name: str
    arguments: Any
    message: Optional[str] = None
    safety_assessment: Optional[Dict[str, Any]] = None


@dataclass
class ApprovalDecisionPayload:
    approval_id: str
    decision: Literal["approved", "rejected"]
    message: Optional[str] = None


@dataclass
class FinalPayload:
    text: str
    structured: Optional[Dict[str, Any]] = None


@dataclass
class ErrorPayload:
    code: Optional[str]
    message: str
    recoverable: Optional[bool] = None
    detail: Optional[Dict[str, Any]] = None


@dataclass
class UsagePayload:
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    cost: Optional[float] = None


@dataclass
class StatePayload:
    state: str = None
    phase: Optional[str] = None
    progress: Optional[float] = None
    avatar_url: Optional[str] = None


ServiceEventPayload = Union[
    TextDeltaPayload,
    ThinkDeltaPayload,
    ToolCallPayload,
    ToolResultPayload,
    ApprovalRequiredPayload,
    ApprovalDecisionPayload,
    FinalPayload,
    ErrorPayload,
    UsagePayload,
    StatePayload,
]


@dataclass
class ClientEventEnvelope:
    event_id: str
    session_id: str
    type: ClientEventType
    ts: float
    source: Literal["client", "system"]
    payload: ClientEventPayload
    agent_id: Optional[str] = None
    trace_id: Optional[str] = None
    version: str = "1.0"


@dataclass
class ServiceEventEnvelope:
    event_id: str
    session_id: str
    type: ServerEventType
    ts: float
    source: Literal["agent", "system", "tool"]
    payload: ServiceEventPayload
    trace_id: Optional[str] = None
    version: str = "1.0"


EventEnvelope = Union[ClientEventEnvelope, ServiceEventEnvelope]
