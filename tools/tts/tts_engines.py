import asyncio
import base64
import os
from pathlib import Path

import edge_tts
import httpx
from fastapi import HTTPException
from openai import AsyncOpenAI
from starlette.responses import StreamingResponse

UPLOAD_FILES_DIR = "uploads"

class TTSEngine:
    """TTS引擎基类"""

    @staticmethod
    def select_server(servers_str: str, index: int) -> str:
        """根据索引选择服务器"""
        servers_list = servers_str.split('\n')
        if len(servers_list) == 1:
            return servers_list[0]
        else:
            # 移除空行
            servers_list = [server for server in servers_list if server.strip()]
            if not servers_list:
                raise ValueError("服务器列表为空")
            return servers_list[index % len(servers_list)]


class EdgeTTSEngine(TTSEngine):
    """Edge TTS引擎"""

    @staticmethod
    async def generate_audio(text: str, tts_settings: dict, index: int):
        """生成Edge TTS音频"""
        edgettsLanguage = tts_settings.get('edgettsLanguage', 'zh-CN')
        edgettsVoice = tts_settings.get('edgettsVoice', 'XiaoyiNeural')
        rate = tts_settings.get('edgettsRate', 1.0)

        full_voice_name = f"{edgettsLanguage}-{edgettsVoice}"
        rate_text = "+0%"
        if rate >= 1.0:
            rate_pent = (rate - 1.0) * 100
            rate_text = f"+{int(rate_pent)}%"
        elif rate < 1.0:
            rate_pent = (1.0 - rate) * 100
            rate_text = f"-{int(rate_pent)}%"

        print(f"Using Edge TTS with voice: {full_voice_name}")

        async def audio_generator():
            communicate = edge_tts.Communicate(text, full_voice_name, rate=rate_text)
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]

        return StreamingResponse(
            audio_generator(),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f"inline; filename=tts_{index}.mp3",
                "X-Audio-Index": str(index)
            }
        )


class CustomTTSEngine(TTSEngine):
    """自定义TTS引擎"""

    @staticmethod
    async def generate_audio(text: str, tts_settings: dict, index: int):
        """生成自定义TTS音频"""
        # 构造 GET 请求参数
        params = {
            "text": text,
            "speaker": tts_settings.get('customTTSspeaker', ''),
            "speed": tts_settings.get('customTTSspeed', 1.0)
        }

        # 选择服务器
        custom_tt_server = TTSEngine.select_server(
            tts_settings.get('customTTSserver', 'http://127.0.0.1:9880'),
            index
        )

        async def audio_generator():
            async with httpx.AsyncClient(timeout=60.0) as client:
                try:
                    # 发起流式 GET 请求到本地 Custom TTS 服务
                    async with client.stream(
                            "GET",
                            custom_tt_server,
                            params=params
                    ) as response:
                        response.raise_for_status()
                        async for chunk in response.aiter_bytes():
                            yield chunk
                except httpx.RequestError as e:
                    print(f"Custom TTS 请求失败: {e}")
                    raise HTTPException(status_code=502, detail=f"Custom TTS 连接失败: {str(e)}")

        return StreamingResponse(
            audio_generator(),
            media_type="audio/wav",
            headers={
                "Content-Disposition": f"inline; filename=tts_{index}.wav",
                "X-Audio-Index": str(index)
            }
        )


class GSVEngine(TTSEngine):
    """GSV TTS引擎"""

    @staticmethod
    def get_sample_steps(index: int) -> int:
        """根据索引获取采样步数"""
        if index == 1:
            return 1
        elif index <= 4:
            return 2
        return 4

    @staticmethod
    async def generate_audio(text: str, tts_settings: dict, index: int):
        """生成GSV音频"""
        audio_path = os.path.join(UPLOAD_FILES_DIR, tts_settings.get('gsvRefAudioPath', ''))
        if not os.path.exists(audio_path):
            # 如果音频文件不存在，则认为是相对路径
            audio_path = tts_settings.get('gsvRefAudioPath', '')

        # 动态样本步数设置
        sample_steps = GSVEngine.get_sample_steps(index)

        # 构建核心请求参数
        gsv_params = {
            "text": text,
            "text_lang": tts_settings.get('gsvTextLang', 'zh'),
            "ref_audio_path": audio_path,
            "prompt_lang": tts_settings.get('gsvPromptLang', 'zh'),
            "prompt_text": tts_settings.get('gsvPromptText', ''),
            "speed_factor": tts_settings.get('gsvRate', 1.0),
            "sample_steps": sample_steps,
            "streaming_mode": True,
            "text_split_method": "cut0",
            "media_type": "ogg",
            "batch_size": 20,
            "seed": 42,
        }

        # 选择服务器
        gsvServer = TTSEngine.select_server(
            tts_settings.get('gsvServer', 'http://127.0.0.1:9880'),
            index
        )

        async def audio_generator():
            async with httpx.AsyncClient(timeout=60.0) as client:
                try:
                    async with client.stream(
                            "POST",
                            f"{gsvServer}/tts",
                            json=gsv_params
                    ) as response:
                        response.raise_for_status()
                        async for chunk in response.aiter_bytes():
                            yield chunk
                except httpx.HTTPStatusError as e:
                    error_detail = f"GSV服务错误: {e.response.status_code} - {await e.response.text()}"
                    raise HTTPException(status_code=502, detail=error_detail)

        return StreamingResponse(
            audio_generator(),
            media_type="audio/ogg",
            headers={
                "Content-Disposition": f"inline; filename=tts_{index}.ogg",
                "X-Audio-Index": str(index)
            }
        )


class OpenAITTSEngine(TTSEngine):
    """OpenAI TTS引擎"""

    @staticmethod
    def validate_config(tts_settings: dict) -> dict:
        """验证OpenAI配置"""
        openai_config = {
            'api_key': tts_settings.get('api_key', ''),
            'model': tts_settings.get('model', 'tts-1'),
            'voice': tts_settings.get('openaiVoice', 'alloy'),
            'speed': tts_settings.get('openaiSpeed', 1.0),
            'base_url': tts_settings.get('base_url', 'https://api.openai.com/v1'),
            'prompt_text': tts_settings.get('gsvPromptText', ''),
            'ref_audio': tts_settings.get('gsvRefAudioPath', '')
        }

        # 验证API密钥
        if not openai_config['api_key']:
            raise HTTPException(status_code=400, detail="OpenAI API密钥未配置")

        return openai_config

    @staticmethod
    async def generate_audio(text: str, tts_settings: dict, index: int):
        """生成OpenAI TTS音频"""
        openai_config = OpenAITTSEngine.validate_config(tts_settings)

        print(f"Using OpenAI TTS with model: {openai_config['model']}, voice: {openai_config['voice']}")

        # 速度限制在0.25到4.0之间
        speed = max(0.25, min(4.0, float(openai_config['speed'])))

        async def audio_generator():
            try:
                # 使用异步OpenAI客户端
                client = AsyncOpenAI(
                    api_key=openai_config['api_key'],
                    base_url=openai_config['base_url']
                )

                if openai_config['ref_audio']:
                    # 使用本地音频文件作为参考
                    audio_file_path = os.path.join(UPLOAD_FILES_DIR, openai_config['ref_audio'])
                    # 读取音频文件并进行base64编码
                    with open(audio_file_path, "rb") as audio_file:
                        audio_data = audio_file.read()
                    # 获取文件扩展名
                    audio_type = Path(audio_file_path).suffix[1:]  # 移除点号
                    # 创建数据URI
                    audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                    audio_uri = f"data:audio/{audio_type};base64,{audio_base64}"

                    # 创建语音请求（带参考音频）
                    response = await client.audio.speech.create(
                        model=openai_config['model'],
                        voice="alloy",
                        input=text,
                        speed=speed,
                        extra_body={
                            "references": [{"text": openai_config['prompt_text'], "audio": audio_uri}]
                        }
                    )
                else:
                    # 创建标准语音请求
                    response = await client.audio.speech.create(
                        model=openai_config['model'],
                        voice=openai_config['voice'],
                        input=text,
                        speed=speed
                    )

                # 获取整个响应内容并分块返回
                content = await response.aread()
                chunk_size = 4096  # 4KB chunks
                for i in range(0, len(content), chunk_size):
                    yield content[i:i + chunk_size]
                    await asyncio.sleep(0)  # 允许其他任务运行

            except Exception as e:
                print(f"OpenAI TTS error: {str(e)}")
                raise HTTPException(status_code=500, detail=f"OpenAI TTS错误: {str(e)}")

        return StreamingResponse(
            audio_generator(),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f"inline; filename=tts_{index}.mp3",
                "X-Audio-Index": str(index)
            }
        )