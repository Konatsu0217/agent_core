import json

from event_bus import EventBus

from tools.tts.stream_audio_player import StreamingAudioPlayer
from src.shared.config.config_manager import ConfigManager
from src.shared.logging.logger import get_logger
from tools.tts.tts_engines import EdgeTTSEngine, CustomTTSEngine, GSVEngine, OpenAITTSEngine

# 配置常量
TTS_CONFIG_FILE = "config/tts.json"
eventBus = EventBus()

class TTSStateTracker:
    def __init__(self, logger):
        self.logger = logger
        self.tts_playing = False  # TTS是否正在播放

    @eventBus.on("tts_state_change")
    def set_tts_playing(self, playing=True):
        """设置TTS播放状态"""
        global can_consume
        self.tts_playing = playing
        can_consume = not playing  # TTS播放时不能消费弹幕
        self.logger.info(f"🎙️ TTS状态: {'播放中' if playing else '已停止'}, 弹幕消费: {'暂停' if playing else '允许'}")

    def get_status(self):
        """获取当前状态"""
        return {
            "tts_playing": self.tts_playing,
            "can_consume": not self.tts_playing
        }

logger = get_logger()
tts_state_tracker = TTSStateTracker(logger)

# TTS引擎工厂
tts_engines = {
    'edgetts': EdgeTTSEngine,
    'customTTS': CustomTTSEngine,
    'GSV': GSVEngine,
    'openai': OpenAITTSEngine
}

# 加载TTS配置
def load_tts_config():
    try:
        with open(TTS_CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"TTS配置文件 {TTS_CONFIG_FILE} 不存在，使用默认配置")
        return get_default_tts_config()
    except json.JSONDecodeError as e:
        logger.error(f"TTS配置文件格式错误: {e}")
        return get_default_tts_config()

def get_default_tts_config():
    return {
        "edgettsLanguage": "zh-CN",
        "edgettsVoice": "XiaoyiNeural",
        "edgettsRate": 1.0,
        "customTTSserver": "http://127.0.0.1:9880",
        "customTTSspeaker": "default_speaker",
        "customTTSspeed": 1.0,
        "gsvServer": "http://127.0.0.1:9880",
        "gsvRefAudioPath": "uploads/reference.wav",
        "gsvTextLang": "zh",
        "gsvPromptLang": "zh",
        "gsvPromptText": "",
        "gsvRate": 1.0,
        "api_key": "",
        "model": "tts-1",
        "openaiVoice": "alloy",
        "openaiSpeed": 1.0,
        "base_url": "https://api.openai.com/v1"
    }

# 加载配置
tts_config = load_tts_config()

global_config = ConfigManager.get_config()
core_server_config = ConfigManager.get_server_config()
backbone_llm_config = ConfigManager.get_backbone_config()

# 临时使用的播放器（后续会根据需求调整）
global_stream_audio_player = StreamingAudioPlayer()
