import asyncio
import json
import websockets
from typing import Dict, Any, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class PEClient:
    def __init__(self, pe_url: str, auto_reconnect: bool = True, max_reconnect_attempts: int = 3):
        self.pe_url = pe_url
        self.websocket = None
        self._connected = False
        self._connect_lock = asyncio.Lock()
        self._auto_reconnect = auto_reconnect
        self._max_reconnect_attempts = max_reconnect_attempts
        self._reconnect_attempts = 0
        self._connection_start_time = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.close()

    @property
    def is_connected(self) -> bool:
        return self._connected and self.websocket is not None

    async def connect(self):
        if self.is_connected:
            return

        async with self._connect_lock:
            if self.is_connected:
                return

            try:
                uri = f"{self.pe_url}/ws/build_prompt"
                self.websocket = await websockets.connect(uri)
                self._connected = True
                self._connection_start_time = datetime.now()
                self._reconnect_attempts = 0
                logger.info("WebSocket连接已建立")
            except Exception as e:
                self._connected = False
                self.websocket = None
                logger.error(f"WebSocket连接失败: {e}")
                raise

    async def ensure_connected(self):
        if not self.is_connected:
            await self.connect()

    async def _try_reconnect(self) -> bool:
        if not self._auto_reconnect:
            return False

        if self._reconnect_attempts >= self._max_reconnect_attempts:
            return False

        self._reconnect_attempts += 1
        logger.warning(f"尝试重连({self._reconnect_attempts}/{self._max_reconnect_attempts})")

        try:
            await self.connect()
            return True
        except Exception:
            return False

    async def close(self):
        if self.is_connected:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.warning(f"关闭WebSocket时错误: {e}")
            finally:
                self.websocket = None
                self._connected = False
                logger.info("WebSocket连接已关闭")

    async def build_prompt(
            self,
            session_id: str,
            user_query: str,
            request_id: Optional[str] = None,
            system_resources: Optional[str] = None,
            stream: bool = False
    ) -> Dict[str, Any]:

        await self.ensure_connected()

        if request_id is None:
            request_id = f"pe_request_{asyncio.current_task().get_name()}"

        req = {
            "type": "build_prompt",
            "request_id": request_id,
            "data": {"session_id": session_id,
                     "user_query": user_query,
                     "system_resources": system_resources,
                     "stream": stream}
        }

        try:
            await self.websocket.send(json.dumps(req))
            resp_raw = await self.websocket.recv()
            resp = json.loads(resp_raw)

            if resp.get("status") == "success":
                return resp.get("data", {})
            else:
                raise ValueError(f"PE请求失败: {resp.get('error')}")

        except websockets.exceptions.WebSocketException as e:
            logger.error(f"WebSocket通信错误: {e}")
            self._connected = False

            if await self._try_reconnect():
                return await self.build_prompt(session_id, user_query, request_id, stream)
            else:
                raise

        except json.JSONDecodeError:
            raise ValueError("无效的JSON响应")
