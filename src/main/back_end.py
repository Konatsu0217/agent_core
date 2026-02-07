# main.py
import asyncio
import json
import time
import uuid
import uvicorn
from fastapi import FastAPI, WebSocket, HTTPException, Body
from typing import Any, Dict
from contextlib import asynccontextmanager

from starlette.middleware.cors import CORSMiddleware
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
from src.agent.storage.sqlite_agent_profile_storage import SQLiteAgentProfileStorage
from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.utils.connet_manager import get_ws_manager
from src.main.session_orchestrator import SessionOrchestrator
from src.infrastructure.logging.logger import get_logger
from src.context.manager import get_context_manager

logger = get_logger()


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
    logger.info("所有服务注册完成")

    # 创建工作流引擎
    workflow_engine = AgentCoordinator()

    # 注册默认agent
    from src.agent.agent_factory import AgentFactory
    agent_profile_storage = SQLiteAgentProfileStorage()
    basic_profile = await AgentFactory.get_basic_agent_profile()
    basic_profile.pop("name", None)
    if basic_profile.get("agent_id") and not agent_profile_storage.exists(basic_profile["agent_id"]):
        agent_profile_storage.create(basic_profile["agent_id"], basic_profile, basic_profile.get("avatar_url"))
    default_agent = AgentFactory.create_agent(basic_profile)
    workflow_engine.register_agent(default_agent)

    # 创建编排器
    orchestrator = SessionOrchestrator(
        workflow_engine=workflow_engine,
        agent_profile_storage=agent_profile_storage,
    )

    # 注册插件
    # tts_plugin = TTSPlugin(event_bus, tts_service, ws_manager)
    # animation_plugin = AnimationPlugin(event_bus, ws_manager)

    app.state.orchestrator = orchestrator
    app.state.ws_manager = ws_manager
    app.state.agent_profile_storage = agent_profile_storage

    yield

    # 清理
    # await event_bus.close()


# 创建FastAPI应用
app = FastAPI(
    title="Agent Core API",
    description="Agent Core 核心服务API",
    version="1.0.0",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该配置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/agent/profile")
async def upload_agent_profile(payload: Dict[str, Any] = Body(...)):
    agent_profile = payload.get("agent_profile") if isinstance(payload, dict) and "agent_profile" in payload else payload
    agent_profile = agent_profile or {}
    agent_profile.pop("name", None)
    agent_id = agent_profile.get("agent_id")
    if not agent_id:
        raise HTTPException(status_code=400, detail="missing_agent_id")
    storage = app.state.agent_profile_storage
    existing = storage.get(agent_id)
    if existing and existing.get("client_readable") is False:
        raise HTTPException(status_code=403, detail="agent_profile_not_overwritable")
    base = None
    if existing:
        base = {k: v for k, v in existing.items() if k != "_meta"}
    merged = _deep_merge(base or {}, agent_profile)
    merged = _preserve_api_keys(base, agent_profile, merged)
    storage.create(agent_id, merged, merged.get("avatar_url"))
    return {"agent_id": agent_id, "status": "upserted"}


def _redact_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = dict(profile)
    backbone = cleaned.get("backbone_llm_config")
    if isinstance(backbone, dict):
        backbone = dict(backbone)
        if "openapi_key" in backbone:
            backbone["openapi_key"] = ""
        if "api_key" in backbone:
            backbone["api_key"] = ""
        cleaned["backbone_llm_config"] = backbone
    return cleaned


def _deep_merge(base: Any, patch: Any) -> Any:
    if isinstance(base, dict) and isinstance(patch, dict):
        merged = dict(base)
        for k, v in patch.items():
            if v is None:
                continue
            if k in merged and isinstance(merged.get(k), dict) and isinstance(v, dict):
                merged[k] = _deep_merge(merged.get(k), v)
            else:
                merged[k] = v
        return merged
    return patch


def _preserve_api_keys(existing: Dict[str, Any] | None, incoming: Dict[str, Any], merged: Dict[str, Any]) -> Dict[str, Any]:
    existing_backbone = (existing or {}).get("backbone_llm_config")
    incoming_backbone = incoming.get("backbone_llm_config")
    merged_backbone = merged.get("backbone_llm_config")
    if not isinstance(merged_backbone, dict):
        return merged

    merged_backbone = dict(merged_backbone)
    for key in ("openapi_key", "api_key"):
        existing_val = None
        if isinstance(existing_backbone, dict):
            existing_val = existing_backbone.get(key)
        incoming_has_key = isinstance(incoming_backbone, dict) and key in incoming_backbone
        if not incoming_has_key:
            continue
        incoming_val = incoming_backbone.get(key)
        if incoming_val is None:
            if existing_val is not None:
                merged_backbone[key] = existing_val
            continue
        if isinstance(incoming_val, str) and incoming_val.strip() == "":
            if existing_val is not None:
                merged_backbone[key] = existing_val

    merged = dict(merged)
    merged["backbone_llm_config"] = merged_backbone
    return merged


@app.get("/api/agent/profile/{agent_id}")
async def get_agent_profile(agent_id: str):
    storage = app.state.agent_profile_storage
    profile = storage.get(agent_id)
    if not profile:
        raise HTTPException(status_code=404, detail="agent_id_not_found")
    if profile.get("client_readable") is False:
        raise HTTPException(status_code=403, detail="agent_profile_not_readable")
    return _redact_profile(profile)


@app.get("/api/session/{session_id}/messages")
async def get_session_messages(session_id: str, agent_id: str, limit: int = 20):
    if limit <= 0:
        limit = 20
    if limit > 200:
        limit = 200
    ctx = get_context_manager().get_latest(session_id, agent_id)
    if not ctx:
        return {"session_id": session_id, "agent_id": agent_id, "messages": []}
    filtered = [m for m in (ctx.messages or []) if isinstance(m, dict) and m.get("role") in {"user", "assistant"}]
    return {"session_id": session_id, "agent_id": agent_id, "messages": filtered[-limit:]}


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


@app.websocket("/ws/agent")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    orchestrator = app.state.orchestrator
    storage = app.state.agent_profile_storage
    session_id = None
    client = websocket.client
    client_addr = f"{client.host}:{client.port}" if client else "unknown"
    logger.info(f"ws_connected client={client_addr}")

    try:
        while True:
            raw_message = await websocket.receive_text()
            message = json.loads(raw_message)
            try:
                envelope = _parse_client_event(message)
            except Exception as e:
                logger.warning(f"ws_message_parse_failed client={client_addr} error={e}")
                continue
            if envelope.type == ClientEventType.INIT_SESSION:
                agent_id = getattr(envelope.payload, "agent_id", None)
                if not agent_id or not storage.get(agent_id):
                    logger.warning(f"ws_invalid_agent_id client={client_addr} agent_id={agent_id}")
                    await websocket.close(code=1008)
                    break
            session_id = envelope.session_id
            await get_ws_manager().cache_websocket(session_id, websocket)
            logger.info(
                f"ws_message_received session_id={session_id} event_type={envelope.type} event_id={envelope.event_id} trace_id={envelope.trace_id}"
            )
            task = asyncio.create_task(orchestrator.handle_client_message(session_id, envelope))
            task.add_done_callback(
                lambda t, s=session_id, e=envelope: logger.error(
                    f"ws_message_handle_failed session_id={s} event_type={e.type} event_id={e.event_id} error={t.exception()}"
                ) if t.exception() else None
            )

    except WebSocketDisconnect as e:
        logger.info(
            f"ws_disconnected session_id={session_id} client={client_addr} code={getattr(e, 'code', None)}"
        )
        if session_id:
            await orchestrator.handle_detach_session(
                session_id,
                DetachSessionPayload(session_id=session_id),
            )


if __name__ == "__main__":
    # 从配置管理器获取服务器配置
    config = ConfigManager.get_config()
    
    host = "0.0.0.0"
    port = config.get('port', 38888)
    workers = config.get('workers', 4)
    limit_concurrency = config.get('limit_concurrency', 50)
    backlog = config.get('backlog', 1024)
    reload = config.get('reload', False)
    timeout_keep_alive = config.get('timeout_keep_alive', 5)
    
    logger.info(f"启动FastAPI服务器在 {host}:{port}")
    logger.info(f"WebSocket端点: ws://{host}:{port}/ws/agent")
    logger.info(f"服务器配置: workers={workers}, limit_concurrency={limit_concurrency}, backlog={backlog}, reload={reload}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        workers=workers,
        limit_concurrency=limit_concurrency,
        backlog=backlog,
        reload=reload,
        timeout_keep_alive=timeout_keep_alive,
        log_level="info",
        access_log=True
    )
