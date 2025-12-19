"""
Agent Core 主服务器
基于FastAPI的基础服务器骨架
"""
import asyncio
import base64
import json
import time
import uuid
from contextlib import asynccontextmanager

import requests
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
from models.danmaku_models import DanmakuData
from tools.danmaku_proxy_service.danmaku_proxy import DanmakuRequest, can_consume
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


@app.post("/api/danmaku/consume")
async def consume_danmaku(data: DanmakuData):
    logger.info(f"consume danmaku: {data}")
    return {"status": "success"}

@app.post("/api/consumption-status")
async def check_consumption_status():
    logger.info(f"check_consumption_status")
    can_consume = True
    return {"can_consume": can_consume}


@app.post("/send_danmaku")
async def send_danmaku(data: DanmakuData):  # 这里要改，对齐bilibli
    logger.info(f"Main Server Received danmaku: {data}")
    request = requests.post(
        "danmaku_proxy_url",
        timeout=5,
        headers={'Content-Type': 'application/json'},
        json=data.dict()
    )
    if request.status_code != 200:
        logger.error(f"Failed to send danmaku: {request.text}")
        raise HTTPException(status_code=500, detail="Failed to send danmaku")

    return {"status": "success"}

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

            chat_msg = {
                "type": "chat_message_reply",
                "data": {
                    "role": "assistant",
                    "content": text,
                    "status": "success"
                }
            }

            await websocket.send_text(json.dumps(chat_msg))

    except WebSocketDisconnect:
        await connect_manager.uncache_websocket(session_id)
        logger.info("WebSocket client disconnected")

    except Exception as e:
        logger.error(f"WebSocket error: {e}")


async def play_tts(text: str, session_id: str):
    await TTSHandler.handle_tts_direct_play(text)

async def get_tts_chunk(text: str, session_id: str):
    async_gen = TTSHandler.handle_tts_for_chunk(text)

    audio_cache = {}

    # 通知开始 TTS
    msg = {
        "type": "ttsStarted",
        "data": {"text": text},
        "timestamp": int(time.time() * 1000)
    }
    await connect_manager.send_msg_to(
        session_id, json.dumps(msg)
    )

    BUFFER_SIZE = 10 * 1024  # 10KB
    audio_buffer = bytearray()

    chunk_index = 0

    async for chunk in async_gen:
        if not chunk:
            continue

        audio_buffer.extend(chunk)

        # 够 10KB 就发
        while len(audio_buffer) >= BUFFER_SIZE:
            send_bytes = audio_buffer[:BUFFER_SIZE]
            del audio_buffer[:BUFFER_SIZE]

            timestamp = int(time.time() * 1000)
            audio_id = f"chunk_{chunk_index}_{timestamp}"

            # ✅ 1. 缓存 raw audio（给后续可能的重放 / 补发）
            audio_cache[audio_id] = audio_buffer

            # ✅ 2. base64 编码
            audio_base64 = base64.b64encode(send_bytes).decode("utf-8")

            # ✅ 3. 构造【最终 VRM 消息】
            vrm_msg = {
                "type": "startSpeaking",
                "data": {
                    "audioId": audio_id,
                    "audioData": audio_base64,
                    "useBase64": True,
                    "chunkIndex": chunk_index,
                    "expressions": []
                },
                "timestamp": timestamp
            }

            # ✅ 4. 直接广播到所有 VRM
            await connect_manager.send_msg_to(
                session_id, json.dumps(vrm_msg)
            )

            chunk_index += 1

        await asyncio.sleep(0.01)

    # ===== flush：不足 10KB 的尾巴 =====
    if audio_buffer:
        timestamp = int(time.time() * 1000)
        audio_id = f"chunk_{chunk_index}_{timestamp}"

        audio_cache[audio_id] = audio_buffer

        audio_base64 = base64.b64encode(audio_buffer).decode("utf-8")

        vrm_msg = {
            "type": "startSpeaking",
            "data": {
                "audioId": audio_id,
                "audioData": audio_base64,
                "useBase64": True,
                "chunkIndex": chunk_index,
                "expressions": []
            },
            "timestamp": timestamp
        }

        await connect_manager.send_msg_to(
            session_id, json.dumps(vrm_msg)
        )


# 修改generate_vrma函数
async def generate_vrma(text: str, session_id: str) -> str:
    # filename = await VRMAHandler.generate_vrma(text)
    filename = "pick_something_up_from_ground.vrma"
    # 构建Web可访问的URL
    timestamp = int(time.time() * 1000)
    vrma_url = f"/vrma_files/{filename}"
    vrm_msg = {
        "type": "vrmaStarted",
        "data": {
            "url": vrma_url,
        },
        "timestamp": timestamp
    }

    await connect_manager.send_msg_to(
        session_id, json.dumps(vrm_msg)
    )



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
