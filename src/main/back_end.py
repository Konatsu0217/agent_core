# main.py
import asyncio
import json
import time
import uuid
import uvicorn
from fastapi import FastAPI, WebSocket
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
from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.utils.connet_manager import get_ws_manager
from src.main.session_orchestrator import SessionOrchestrator
from src.infrastructure.logging.logger import get_logger

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
