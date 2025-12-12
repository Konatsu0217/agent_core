import json
import logging
from typing import List, Dict

from starlette.websockets import WebSocket


class PlayWSManager:
    def __init__(self):
        self.cache: Dict[str, WebSocket] = {}

    async def cache_websocket(self, session_id: str, websocket: WebSocket):
        self.cache[session_id] = websocket
        logging.info(f"Main interface connected. Total: {len(self.cache)}")

    async def uncache_websocket(self, session_id: str, websocket: WebSocket):
        logging.info(f"Main interface disconnected. Total: {len(self.cache)}")
        del self.cache[session_id]

    async def broadcast_websocket(self, msg: str, websocket: WebSocket):
        logging.info(f"Main interface broadcast. Total: {len(self.cache)}")
        for session_id, websocket in self.cache.items():
            await websocket.send_text(msg)

    async def send_chunk_to(self, session_id: str, msg: bytes):
        websocket = self.cache.get(session_id)
        if websocket:
            await websocket.send_bytes(msg)

    async def send_json_to(self, session_id: str, msg: dict):
        websocket = self.cache.get(session_id)
        if websocket:
            await websocket.send_json(msg)

    async def send_msg_to(self, session_id: str, chunk: str):
        websocket = self.cache.get(session_id)
        if websocket:
            await websocket.send_text(chunk)






















