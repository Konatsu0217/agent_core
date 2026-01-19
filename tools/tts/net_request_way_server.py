from typing import AsyncGenerator

from fastapi import FastAPI, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

from global_statics import tts_engines, tts_config
from src.shared.utils.connet_manager import PlayWSManager
from src.shared.logging.logger import get_logger

# 4. 创建FastAPI应用实例
app = FastAPI(
    title="TTS + VRM Service",
    description="玩法服务",
    version="1.0.0"
)

# 5. 配置CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

connect_manager = PlayWSManager()
logger = get_logger()


class TTSRequest(BaseModel):
    index: int = Field(..., description="消息索引")
    text: str = Field(..., description="文本内容")
    engine: str = Field(..., description="TTS引擎选择")  # 引擎选择从请求传入
    voice: str = Field(default="default", description="语音选择")


@app.post("/tts")
async def text_to_speech(data: TTSRequest = Body(...)):
    """TTS主方法 - 使用策略模式调用不同引擎"""
    try:
        text = data.text
        if text == "":
            return JSONResponse(status_code=400, content={"error": "Text is empty"})
        # 获取语音配置
        voice = data.voice
        tts_settings = tts_config.copy()

        # 如果使用特定的语音配置
        if voice != 'default' and voice in tts_config.get('newtts', {}):
            tts_settings.update(tts_config['newtts'][voice])

        index = data.index
        tts_engine = data.engine  # 直接从请求获取引擎类型，不再从配置读取

        # 使用策略模式选择对应的TTS引擎
        engine_class = tts_engines.get(tts_engine)
        if not engine_class:
            raise HTTPException(status_code=400, detail=f"不支持的TTS引擎: {tts_engine}")

        # 调用对应的引擎生成音频
        return await engine_class.generate_audio(text, tts_settings, index)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTS处理错误: {str(e)}")
        return JSONResponse(status_code=500, content={"error": f"服务器内部错误: {str(e)}"})

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
