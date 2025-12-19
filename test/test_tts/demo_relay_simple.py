#!/usr/bin/env python3
"""
TTS到WebSocket中继服务 - 简化版本
专注于核心功能：将TTS流式音频转发到WebSocket
"""

import asyncio
import base64
import json
import logging
import time
import httpx
import websockets
from typing import Optional

from tools.tts.function_call_way import generate_tts_audio

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TTSWebSocketRelay:
    """TTS到WebSocket中继器"""

    def __init__(self, tts_url: str = "http://localhost:8000/tts",
                 websocket_url: str = "ws://localhost:3456/ws/tts"):
        self.tts_url = tts_url
        self.websocket_url = websocket_url
        self.websocket = None
        self.is_connected = False

    async def connect_websocket(self) -> bool:
        """连接WebSocket"""
        try:
            self.websocket = await websockets.connect(self.websocket_url)
            self.is_connected = True
            logger.info(f"✅ 已连接到WebSocket: {self.websocket_url}")
            return True
        except Exception as e:
            logger.error(f"❌ 连接WebSocket失败: {e}")
            self.is_connected = False
            return False

    async def disconnect_websocket(self):
        """断开WebSocket连接"""
        if self.websocket:
            await self.websocket.close()
            self.is_connected = False
            logger.info("🔌 WebSocket连接已关闭")

    async def relay_tts_to_websocket(self, text: str, voice: str = "default", engine: str = "edgetts"):
        """流式TTS转发到WebSocket"""
        # 直接调用生成器方法
        # 发送开始信号
        start_msg = {
            "type": "ttsStarted",
            "data": {
                "text": text,
                "engine": engine,
                "voice": voice,
                "timestamp": int(time.time() * 1000)
            }
        }
        await self.websocket.send(json.dumps(start_msg))

        chunk_index = 0
        audio_index = 0

        async for audio_chunk in generate_tts_audio(text, engine):
            # Base64编码
            audio_base64 = base64.b64encode(audio_chunk).decode('utf-8')
            audio_data_url = f"data:audio/mpeg;base64,{audio_base64}"
            chunk_size = len(audio_chunk)

            # 构建音频块消息
            audio_msg = {
                "type": "startSpeaking",
                "data": {
                    "audioUrl": audio_data_url,
                    "audioDataUrl": audio_data_url,
                    "chunkIndex": chunk_index,
                    "chunkSize": chunk_size,
                    "audioIndex": audio_index,
                    "expressions": [],
                    "timestamp": int(time.time() * 1000)
                }
            }
            # 发送到WebSocket
            await self.websocket.send(json.dumps(audio_msg))
            logger.info(f"📤 转发音频块 {chunk_index}: {chunk_size} bytes")
            chunk_index += 1
            # 小延迟避免过载
            await asyncio.sleep(0.05)

    async def relay_tts_to_websocket_net(self, text: str, engine: str = "edgetts",
                                         voice: str = "default", chunk_size: int = 4096) -> bool:
        """将TTS音频流式转发到WebSocket"""

        if not self.is_connected:
            logger.error("❌ WebSocket未连接")
            return False

        logger.info(f"🚀 开始TTS流式转发: '{text[:50]}...'")

        try:
            # 准备TTS请求
            tts_request = {
                "index": int(time.time() * 1000) % 100000,
                "text": text,
                "engine": engine,
                "voice": voice
            }

            # 发送开始信号
            start_msg = {
                "type": "ttsStarted",
                "data": {
                    "text": text,
                    "engine": engine,
                    "voice": voice,
                    "timestamp": int(time.time() * 1000)
                }
            }
            await self.websocket.send(json.dumps(start_msg))

            # 发送TTS请求并流式接收
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", self.tts_url, json=tts_request) as response:

                    if response.status_code != 200:
                        logger.error(f"TTS请求失败: {response.status_code}")
                        return False

                    logger.info("✅ TTS请求成功，开始流式转发")

                    # 获取音频索引
                    audio_index = response.headers.get('X-Audio-Index', '0')
                    chunk_index = 0
                    total_bytes = 0

                    # 流式接收并转发
                    async for chunk in response.aiter_bytes():
                        if chunk:
                            chunk_size = len(chunk)
                            total_bytes += chunk_size

                            # Base64编码
                            audio_base64 = base64.b64encode(chunk).decode('utf-8')
                            audio_data_url = f"data:audio/mpeg;base64,{audio_base64}"

                            # 构建音频块消息
                            audio_msg = {
                                "type": "startSpeaking",
                                "data": {
                                    "audioUrl": audio_data_url,
                                    "audioDataUrl": audio_data_url,
                                    "chunkIndex": chunk_index,
                                    "chunkSize": chunk_size,
                                    "audioIndex": audio_index,
                                    "expressions": [],
                                    "timestamp": int(time.time() * 1000)
                                }
                            }

                            # 发送到WebSocket
                            await self.websocket.send(json.dumps(audio_msg))
                            logger.info(f"📤 转发音频块 {chunk_index}: {chunk_size} bytes")

                            chunk_index += 1

                            # 小延迟避免过载
                            await asyncio.sleep(0.05)

                    # 发送完成信号
                    complete_msg = {
                        "type": "stopSpeaking",
                        "data": {
                            "totalChunks": chunk_index,
                            "totalBytes": total_bytes,
                            "audioIndex": audio_index
                        }
                    }
                    await self.websocket.send(json.dumps(complete_msg))

                    logger.info(f"✅ TTS流式转发完成: {chunk_index} 块, {total_bytes} bytes")
                    return True

        except Exception as e:
            logger.error(f"❌ TTS流式转发失败: {e}")

            # 发送错误信号
            error_msg = {
                "type": "ttsStreamError",
                "data": {
                    "error": str(e),
                    "timestamp": int(time.time() * 1000)
                }
            }
            try:
                await self.websocket.send(json.dumps(error_msg))
            except:
                pass

            return False

    async def listen_websocket(self):
        """监听WebSocket消息"""
        try:
            async for message in self.websocket:
                data = json.loads(message)
                logger.info(f"📨 收到WebSocket消息: {data.get('type', 'unknown')}")
        except websockets.exceptions.ConnectionClosed:
            logger.info("🔌 WebSocket连接已关闭")
            self.is_connected = False
        except Exception as e:
            logger.error(f"❌ WebSocket监听错误: {e}")
            self.is_connected = False


async def main():
    """主函数"""

    # 创建中继器
    relay = TTSWebSocketRelay()

    try:
        # 连接WebSocket
        if not await relay.connect_websocket():
            return

        # 启动监听任务
        listen_task = asyncio.create_task(relay.listen_websocket())

        # 测试文本
        test_texts = [
            "你好，这是一个TTS到WebSocket的中继测试。",
            "音频数据会以流式方式转发到WebSocket。",
            "支持实时播放和分块传输。"
        ]

        logger.info("🚀 开始测试中继服务...")

        # 逐个转发文本
        for i, text in enumerate(test_texts):
            logger.info(f"\n{'=' * 50}")
            logger.info(f"🔢 第 {i + 1} 个文本: {text}")
            await relay.relay_tts_to_websocket(text)

            # success = await relay.relay_tts_to_websocket_net(text)
            # if not success:
            #     logger.error(f"❌ 第 {i+1} 个文本转发失败")
            #     break

            # 等待一段时间再发送下一个
            await asyncio.sleep(2)

        logger.info("\n✅ 所有测试完成")

        # 等待一段时间让监听任务完成
        await asyncio.sleep(2)

        # 取消监听任务
        listen_task.cancel()

    except KeyboardInterrupt:
        logger.info("\n🛑 用户中断测试")
    except Exception as e:
        logger.error(f"❌ 测试过程错误: {e}")
    finally:
        await relay.disconnect_websocket()


if __name__ == "__main__":
    print("🚀 TTS到WebSocket中继服务 - 简化版本")
    print("=" * 60)
    print("📡 TTS服务器: http://localhost:8000/tts")
    print("🔗 WebSocket: ws://localhost:5175/ws/vrm")
    print("=" * 60)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 程序被中断")
