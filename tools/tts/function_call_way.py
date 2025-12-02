from typing import AsyncGenerator

from global_statics import tts_config, tts_engines


async def generate_tts_audio(
        text: str,
        engine: str = "edgetts",
        voice: str = "default",
        index: int = 1
) -> AsyncGenerator[bytes, None]:
    """
    流式生成TTS音频数据
    :param text: 要转换的文本
    :param engine: TTS引擎
    :param voice: 语音选择
    :param index: 音频索引
    :yield: 音频字节块
    """

    # 获取TTS配置
    tts_settings = tts_config.copy()
    if voice != 'default' and voice in tts_config.get('newtts', {}):
        tts_settings.update(tts_config['newtts'][voice])

    # 选择引擎
    engine_class = tts_engines.get(engine)
    if not engine_class:
        raise ValueError(f"不支持的TTS引擎: {engine}")

    # 调用引擎生成音频（返回StreamingResponse）
    response = await engine_class.generate_audio(text, tts_settings, index)

    # 流式读取音频数据
    async for chunk in response.body_iterator:
        yield chunk