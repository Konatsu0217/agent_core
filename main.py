"""
Agent Core 主服务器
基于FastAPI的基础服务器骨架
"""
import asyncio
import json
import uuid
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.params import Query
from starlette.websockets import WebSocketDisconnect, WebSocket

import global_statics
from core.fast_agent import FastAgent
from global_statics import logger
from handlers.tts_handler import TTSHandler
from fastapi.staticfiles import StaticFiles
from handlers.vrma_handler import VRMAHandler
from models.agent_data_models import AgentRequest
from utils.config_manager import ConfigManager
from utils.connet_manager import PlayWSManager
from clients.session_manager import get_session_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("Agent Core 服务器启动中...")

    # 加载配置
    config = global_statics.global_config
    logger.info(f"配置加载完成: port={config['port']}, workers={config['workers']}")

    yield

    # 关闭时执行
    logger.info("Agent Core 服务器关闭中...")


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

fast_agent = FastAgent(use_tools=False)
connect_manager = PlayWSManager()
session_manager = get_session_manager()
vrma_files_dir = 'tools/motion_drive/'
app.mount("/vrma_files", StaticFiles(directory=vrma_files_dir), name="vrma_files")


@app.get("/")
async def root():
    """根路径，返回服务状态"""
    return {
        "service": "Agent Core",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "service": "Agent Core"
    }


@app.get("/config")
async def get_config():
    """获取当前配置信息（不包含敏感信息）"""
    try:
        config = ConfigManager.get_config()
        # 返回非敏感配置信息
        safe_config = {
            "port": config.get("port"),
            "workers": config.get("workers"),
            "limit_concurrency": config.get("limit_concurrency"),
            "backlog": config.get("backlog"),
            "reload": config.get("reload"),
            "timeout_keep_alive": config.get("timeout_keep_alive"),
            "pe_url": config.get("pe_url"),
            "rag_url": config.get("rag_url"),
            "mcphub_url": config.get("mcphub_url")
        }
        return safe_config
    except Exception as e:
        logger.error(f"获取配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail="配置获取失败")


@app.get("/status")
async def get_status():
    """获取服务状态信息"""
    from global_statics import tts_state_tracker

    tts_status = tts_state_tracker.get_status()

    return {
        "service": "Agent Core",
        "status": "running",
        "tts_status": tts_status
    }

# Todo: 调度器
# orchestrator = AgentOrchestrator(settings)

# @app.post("/agent/query")
# async def handle_query(request: AgentRequest) -> AgentResponse:
#     return await orchestrator.process_query(request)

@app.post("/test/query")
async def get_agent_query(request_json: dict[str, str]):
    user_input = request_json.get("query", "")

    request = AgentRequest(
        query=user_input
    )

    response = await fast_agent.process(
        request
    )

    text = response.response.get('response', '')
    asyncio.create_task(play_tts(text))
    asyncio.create_task(generate_vrma(text))

    return {
        "role": "assistant",
        "content": text,
        "status": "success"
    }

@app.get("/get_ws_session_id")
async def get_ws_session_id():
    session_id = str(uuid.uuid4())
    return {
        "session_id": session_id
    }

@app.get("/get_tool_list")
async def get_tool_list(session_id: str = Query()):
    return fast_agent.mcp_tool_cache


@app.websocket("/ws/agent/query")
async def websocket_agent_query(websocket: WebSocket, session_id: str = Query()):
    await websocket.accept()
    logger.info(f"WebSocket会话 {session_id} 已建立")
    await connect_manager.cache_websocket(session_id, websocket)

    try:
        while True:
            message = await websocket.receive()

            if "text" not in message:
                continue

            request_json = json.loads(message["text"])

            user_input = request_json.get("query", "")
            if not user_input:
                continue

            session_id = request_json.get("session_id", session_id)

            # session_id 获取会话维度的 历史消息、记忆、工具列表与可用性

            # 代理请求
            response = await fast_agent.process(AgentRequest(query=user_input, session_id=session_id))

            raw = response.response
            text = raw.get("response", "") if isinstance(raw, dict) else str(raw)

            # 缓存会话历史记录
            asyncio.create_task(session_manager.add_session_value(session_id,agent_id="DefaultAgent", value={"role": "user", "content": user_input}))
            asyncio.create_task(session_manager.add_session_value(session_id,agent_id="DefaultAgent", value={"role": "assistant", "content": text}))

            # 后台任务
            t1 = asyncio.create_task(get_tts_chunk(text, session_id))
            t1.add_done_callback(lambda t: logger.info(f"TTS finished: {t.exception()}"))

            t2 = asyncio.create_task(generate_vrma(text, session_id))
            t2.add_done_callback(lambda t: logger.info(f"VRMA finished: {t.exception()}"))

            await websocket.send_json({
                "role": "assistant",
                "content": text,
                "status": "success"
            })

    except WebSocketDisconnect:
        await connect_manager.uncache_websocket(session_id)
        logger.info("WebSocket client disconnected")

    except Exception as e:
        logger.error(f"WebSocket error: {e}")


async def play_tts(text: str, session_id: str):
    await TTSHandler.handle_tts_direct_play(text)

async def get_tts_chunk(text: str, session_id: str):
    async_gen = TTSHandler.handle_tts_for_chunk(text)

    async for chunk in async_gen:
        await connect_manager.send_chunk_to(session_id, chunk)

    # 所有块发送完毕
    await connect_manager.send_msg_to(session_id, json.dumps({
        "type": "tts_end",
        "session_id": session_id
    }))

# 修改generate_vrma函数
async def generate_vrma(text: str, session_id: str) -> str:
    filename = await VRMAHandler.generate_vrma(text)
    # 构建Web可访问的URL
    vrma_url = f"/vrma_files/{filename}"
    await connect_manager.send_json_to(session_id, {
        "type": "vrma_action",
        "url": vrma_url
    })


def main():
    """主函数，启动服务器"""
    config = ConfigManager.get_config()

    logger.info(f"启动主服务: http://0.0.0.0:{config['port']}")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config['port'],
        workers=config['workers'],
        limit_concurrency=config['limit_concurrency'],
        backlog=config['backlog'],
        reload=config['reload'],
        timeout_keep_alive=config['timeout_keep_alive'],
        log_level="error"
    )

async def async_init():
    await fast_agent.initialize()

if __name__ == "__main__":
    asyncio.run(async_init())
    main()
