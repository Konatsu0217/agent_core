import asyncio
import time
from typing import AsyncGenerator

import global_statics
from tools.tts.function_call_way import generate_tts_audio

logger = global_statics.logger

class TTSHandler:
    def __init__(self):
        self.name = "tts_handler"

    @staticmethod
    async def handle_tts_for_chunk(text: str, engine: str = "edgetts", voice: str = "default", index: int = 1) -> AsyncGenerator[bytes, None]:
        """
        处理TTS请求，返回音频流
        :param text: 要转换的文本
        :param engine: TTS引擎
        :param voice: 语音选择
        :param index: 音频索引
        :yield: 音频字节块
        """
        async for chunk in generate_tts_audio(text, engine, voice, index):
            yield chunk

    @staticmethod
    async def handle_tts_direct_play(text: str, engine: str = "edgetts", voice: str = "default", index: int = 1) -> AsyncGenerator[bytes, None]:
        """
        处理TTS请求，返回音频流
        :param text: 要转换的文本
        :param engine: TTS引擎
        :param voice: 语音选择
        :param index: 音频索引
        :yield: 音频字节块
        """
        player = global_statics.global_stream_audio_player

        try:
            # 记录开始时间
            start_time = time.time()

            # 启动播放线程
            player.is_playing = True
            player.is_receiving = True
            player.start_playback_thread()

            # 等待播放线程启动
            await asyncio.sleep(0.5)
            logger.info(f"📡 开始请求TTS音频流... time = {time.time()}")
            # 标记是否接收到第一个音频包
            first_chunk_received = False
            chunk_count = 0
            total_bytes = 0
            # 🔑 调用 handle_tts_for_chunk 获取音频流
            async for chunk in TTSHandler.handle_tts_for_chunk(
                    text=text,
                    engine=engine,
                    voice=voice,
                    index=index
            ):
                if chunk:  # 过滤掉空块
                    # 标记接收到第一个音频包
                    if not first_chunk_received:
                        first_chunk_received = True
                        first_chunk_time = time.time() - start_time
                        logger.info(f"🎵 接收到第一个音频包: {len(chunk)} bytes (耗时 {first_chunk_time:.2f}s)")

                    # 按顺序添加音频数据到播放队列
                    player.add_audio_chunk(chunk)

                    # 统计信息
                    chunk_count += 1
                    total_bytes += len(chunk)

            # 检查是否接收到音频数据
            if not first_chunk_received:
                logger.warning("未接收到任何音频数据")
                player.stop_playback()
                return False

            # 标记接收完成
            player.stop_receiving()

            logger.info(f"📊 接收完成: 总大小={total_bytes / 1024:.1f}KB, 音频块数={chunk_count}, 播放队列={player.audio_queue.qsize()} 块待播放, 总耗时={time.time() - start_time:.2f}s")

            # 等待播放完成
            logger.info("⏳ 等待播放完成...")
            player.wait_for_completion()

            logger.info("播放完成")
            return True

        except Exception as e:
            logger.exception(f"TTS播放失败: {e}")
            player.stop_playback()
            return False


if __name__ == "__main__":
    asyncio.run(TTSHandler.handle_tts_direct_play("你好, 这是一个tts流式获取并且播放的测试脚本"))
