import json
import logging
from typing import List, Dict

from starlette.websockets import WebSocket


class PlayWSManager:
    def __init__(self):
        self.main_connections: List[WebSocket] = []  # 到前端页的ws
        self.vrm_connections: List[WebSocket] = []   # 动作系统的ws
        self.tts_connections: List[WebSocket] = []   # tts的ws
        self.audio_cache: Dict[str, bytes] = {}  # 缓存音频数据

    async def connect_main(self, websocket: WebSocket):
        await websocket.accept()
        self.main_connections.append(websocket)
        logging.info(f"Main interface connected. Total: {len(self.main_connections)}")

    async def connect_vrm(self, websocket: WebSocket):
        await websocket.accept()
        self.vrm_connections.append(websocket)
        logging.info(f"VRM interface connected. Total: {len(self.vrm_connections)}")

    async def connect_tts(self, websocket: WebSocket):
        await websocket.accept()
        self.tts_connections.append(websocket)
        logging.info(f"TTS interface connected. Total: {len(self.tts_connections)}")

    async def disconnect_main(self, websocket: WebSocket):
        self.main_connections.remove(websocket)
        logging.info(f"Main interface disconnected. Total: {len(self.main_connections)}")

    async def disconnect_vrm(self, websocket: WebSocket):
        self.vrm_connections.remove(websocket)
        logging.info(f"VRM interface disconnected. Total: {len(self.vrm_connections)}")

    async def disconnect_tts(self, websocket: WebSocket):
        self.tts_connections.remove(websocket)
        logging.info(f"TTS interface disconnected. Total: {len(self.tts_connections)}")

    async def broadcast_to(self, message: dict, who: str = "main"):
        message = json.dumps(message)
        disconnected = []
        target = self.main_connections if who == "main" else self.vrm_connections if who == "vrm" else self.tts_connections

        for connection in target:
            try:
                await connection.send_text(message)
            except Exception as e:
                logging.error(f"Error sending message to {who} connection: {e}")
                disconnected.append(connection)

        if disconnected:
            logging.info(f"Disconnected {len(disconnected)} {who} connections after broadcast")
            for conn in disconnected:
                await self.disconnect_main(conn) if who == "main" else await self.disconnect_vrm(conn) if who == "vrm" else await self.disconnect_tts(conn)



    def cache_audio(self, audio_id: str, audio_data: bytes):
        """缓存音频数据"""
        self.audio_cache[audio_id] = audio_data

    def get_cached_audio(self, audio_id: str) -> bytes:
        """获取缓存的音频数据"""
        return self.audio_cache.get(audio_id)






















