"""
Agent Core 主服务器
基于FastAPI的基础服务器骨架
"""
import asyncio
import json

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from starlette.websockets import WebSocketDisconnect, WebSocket

import global_statics
from clients.llm_client import LLMClientManager
from core.fast_agent import FastAgent
from handlers.tts_handler import TTSHandler
from handlers.vrma_handler import VRMAHandler
from models.agent_data_models import AgentRequest, AgentResponse
from utils.config_manager import ConfigManager
from global_statics import logger, eventBus



@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("🚀 Agent Core 服务器启动中...")

    # 加载配置
    config = global_statics.global_config
    logger.info(f"配置加载完成: port={config['port']}, workers={config['workers']}")

    yield

    # 关闭时执行
    logger.info("🛑 Agent Core 服务器关闭中...")


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

fast_agent = FastAgent(use_tools=True)

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

@app.websocket("/ws/agent/query")
async def websocket_agent_query(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            message = await websocket.receive()

            if "text" not in message:
                continue

            request_json = json.loads(message["text"])

            user_input = request_json.get("query", "")
            if not user_input:
                continue

            # 代理请求
            response = await fast_agent.process(AgentRequest(query=user_input))

            raw = response.response
            text = raw.get("response", "") if isinstance(raw, dict) else str(raw)

            # 后台任务
            t1 = asyncio.create_task(play_tts(text))
            t1.add_done_callback(lambda t: print("TTS finished", t.exception()))

            t2 = asyncio.create_task(generate_vrma(text))
            t2.add_done_callback(lambda t: print("VRMA finished", t.exception()))

            await websocket.send_json({
                "role": "assistant",
                "content": text,
                "status": "success"
            })

    except WebSocketDisconnect:
        print("WebSocket client disconnected")

    except Exception as e:
        print("Error:", e)


async def play_tts(text: str):
    # await TTSHandler.handle_tts_direct_play(text)
    pass

async def generate_vrma(text: str) -> str:
    # await VRMAHandler.generate_vrma(text)
    pass


def main():
    """主函数，启动服务器"""
    config = ConfigManager.get_config()

    logger.info(f"启动服务器: http://0.0.0.0:{config['port']}")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config['port'],
        workers=config['workers'],
        limit_concurrency=config['limit_concurrency'],
        backlog=config['backlog'],
        reload=config['reload'],
        timeout_keep_alive=config['timeout_keep_alive']
    )

async def async_init():
    await fast_agent.initialize()

if __name__ == "__main__":
    asyncio.run(async_init())
    main()