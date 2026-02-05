# main.py
import json
import time
import uuid
from fastapi import FastAPI, WebSocket
from contextlib import asynccontextmanager

from starlette.websockets import WebSocketDisconnect

from src.coordinator.agent_coordinator import AgentCoordinator
from src.di.services.impl.mem0_memory_service import Mem0MemoryService
from src.domain.events import (
    ClientEventType,
    ClientEventEnvelope,
    UserMessagePayload,
    ToolApprovalPayload,
    HeartbeatPayload,
    InitSessionPayload,
    AttachSessionPayload,
    DetachSessionPayload,
    DeleteSessionPayload,
)
from src.infrastructure.utils.connet_manager import get_ws_manager
from src.main.session_orchestrator import SessionOrchestrator


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 初始化组件
    ws_manager = get_ws_manager()

    # 初始化服务容器
    from src.di.container import get_service_container
    from src.di.services.impl.default_query_wrapper_service import DefaultQueryWrapper
    from src.di.services.impl.mcp_tool_manager import McpToolManager
    from src.di.services.impl.pe_prompt_service import PePromptService
    from src.di.services.impl.default_session_service import DefaultSessionService

    # 获取服务容器
    container = get_service_container()
    # 注册服务
    container.register("query_wrapper", DefaultQueryWrapper())
    container.register("tool_manager", McpToolManager())
    container.register("memory_service", Mem0MemoryService())
    container.register("prompt_service", PePromptService())
    container.register("session_service", DefaultSessionService())
    print("✅ 所有服务注册完成")

    # 创建工作流引擎
    workflow_engine = AgentCoordinator()

    # 注册默认agent
    from src.agent.agent_factory import AgentFactory
    default_agent = await AgentFactory.get_basic_agent()
    workflow_engine.register_agent(default_agent)

    # 创建编排器
    orchestrator = SessionOrchestrator(
        workflow_engine=workflow_engine
    )

    # 注册插件
    # tts_plugin = TTSPlugin(event_bus, tts_service, ws_manager)
    # animation_plugin = AnimationPlugin(event_bus, ws_manager)

    app.state.orchestrator = orchestrator
    app.state.ws_manager = ws_manager

    yield

    # 清理
    # await event_bus.close()


app = FastAPI(lifespan=lifespan)


def _build_client_payload(event_type: ClientEventType, payload: dict, session_id: str):
    if event_type == ClientEventType.USER_MESSAGE:
        return UserMessagePayload(
            text=payload.get("text", ""),
            session_id=session_id,
            attachments=payload.get("attachments"),
            metadata=payload.get("metadata"),
        )
    if event_type == ClientEventType.TOOL_APPROVAL:
        return ToolApprovalPayload(
            approval_id=payload.get("approval_id", ""),
            session_id=session_id,
            decision=payload.get("decision", "rejected"),
            message=payload.get("message"),
        )
    if event_type == ClientEventType.HEARTBEAT:
        return HeartbeatPayload(
            session_id=session_id,
            client_time=payload.get("client_time", time.time()),
        )
    if event_type == ClientEventType.INIT_SESSION:
        return InitSessionPayload(
            user_id=payload.get("user_id"),
            agent_id=payload.get("agent_id"),
            metadata=payload.get("metadata"),
            plugin_config=payload.get("plugin_config"),
        )
    if event_type == ClientEventType.ATTACH_SESSION:
        return AttachSessionPayload(
            session_id=session_id,
            metadata=payload.get("metadata"),
        )
    if event_type == ClientEventType.DETACH_SESSION:
        return DetachSessionPayload(
            session_id=session_id,
            reason=payload.get("reason"),
        )
    if event_type == ClientEventType.DELETE_SESSION:
        return DeleteSessionPayload(
            session_id=session_id,
            reason=payload.get("reason"),
        )
    raise ValueError("unsupported_client_event")


def _parse_client_event(message: dict) -> ClientEventEnvelope:
    event_type = ClientEventType(message.get("type"))
    payload = message.get("payload") or {}
    session_id = message.get("session_id") or payload.get("session_id")
    if not session_id:
        raise ValueError("missing_session_id")
    return ClientEventEnvelope(
        event_id=message.get("event_id", str(uuid.uuid4())),
        session_id=session_id,
        type=event_type,
        ts=message.get("ts", time.time()),
        source=message.get("source", "client"),
        payload=_build_client_payload(event_type, payload, session_id),
        trace_id=message.get("trace_id"),
        version=message.get("version", "1.0"),
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    orchestrator = app.state.orchestrator
    session_id = None

    try:
        while True:
            raw_message = await websocket.receive_text()
            message = json.loads(raw_message)
            try:
                envelope = _parse_client_event(message)
            except Exception:
                continue
            session_id = envelope.session_id
            await orchestrator.handle_client_message(session_id, envelope)

    except WebSocketDisconnect:
        if session_id:
            await orchestrator.handle_detach_session(
                session_id,
                DetachSessionPayload(session_id=session_id),
            )
