import asyncio
import base64
import json
import time
import uuid
from typing import Dict

from fastapi import WebSocket, WebSocketDisconnect, Query
from starlette.websockets import WebSocket

import global_statics
from global_statics import logger
from src.agent.fast_agent import FastAgent
from src.domain.models.agent_data_models import AgentRequest
from src.infrastructure.clients.session_manager import get_session_manager
from src.infrastructure.handlers.tts_handler import TTSHandler
from src.infrastructure.handlers.vrma_handler import VRMAHandler
from src.shared.utils.connet_manager import PlayWSManager
from test.test_proactive_module import DemoProactiveModule


class WebSocketHandler:
    def __init__(self):
        self.connect_manager = PlayWSManager()
        self.session_manager = get_session_manager()
        self.fast_agent = FastAgent(use_tools=True)
        self.proactive_schedular = DemoProactiveModule()

    async def websocket_agent_query(self, websocket: WebSocket, session_id: str = Query()):
        await websocket.accept()
        logger.info(f"WebSocket会话 {session_id} 已建立")
        await self.connect_manager.cache_websocket(session_id, websocket)
        await self.proactive_schedular.register_session(session_id)

        try:
            while True:
                message = await websocket.receive()

                if "text" not in message:
                    continue

                request_json = json.loads(message["text"])

                user_input = request_json.get("query", "")
                if not user_input:
                    continue

                await self.proactive_schedular.touch(session_id)

                session_id = request_json.get("session_id", session_id)

                imgBase64: list[str] = request_json.get("images_b64", [])

                raw_response = await self.fast_agent.process(
                    AgentRequest(query=user_input, extraInfo={"images_b64": imgBase64}, session_id=session_id))

                llm_reply = raw_response.response

                text = llm_reply.get("response", "")
                action_command = llm_reply.get("action", "")
                expression = llm_reply.get("expression", "")

                asyncio.create_task(self.session_manager.add_session_value(session_id, agent_id="DefaultAgent",
                                                                          value={"role": "user", "content": user_input}))
                asyncio.create_task(self.session_manager.add_session_value(session_id, agent_id="DefaultAgent",
                                                                          value={"role": "assistant", "content": text}))

                t1 = asyncio.create_task(self.get_tts_chunk(text, session_id))
                t1.add_done_callback(lambda t: logger.info(f"TTS finished: {t.exception()}"))

                if action_command:
                    t2 = asyncio.create_task(self.generate_vrma(action_command, session_id))
                    t2.add_done_callback(lambda t: logger.info(f"VRMA finished: {t.exception()}"))

                chat_msg = {
                    "type": "chat_message_reply",
                    "data": {
                        "role": "assistant",
                        "content": text,
                        "status": "success"
                    }
                }

                await websocket.send_text(json.dumps(chat_msg))

        except WebSocketDisconnect:
            await self.connect_manager.uncache_websocket(session_id)
            await self.proactive_schedular.unregister_session(session_id)
            logger.info("WebSocket client disconnected")

        except Exception as e:
            await self.connect_manager.uncache_websocket(session_id)
            await self.proactive_schedular.unregister_session(session_id)
            logger.error(f"WebSocket error: {e}")

    async def handle_proactive_trigger(self, session_id: str):
        websocket = await self.connect_manager.get_websocket(session_id)
        if websocket is None:
            logger.info(f"[Proactive] session {session_id} offline, skip")
            return

        fake_user_query = (
            """
            你现在是主动发起对话，而不是在回答问题。如果用户多次没有主动回复你的消息，你应该输出更加有意义，带询问和思考的内容
            "宝宝你在忙吗～" 
            "最近在看什么有趣的事情呢？"
            "我在想你最近在看什么有趣的视频,可以和我分享一下吗"

            要求：
            - 不要像提问或开场白，而是直接开始说话
            - 不要复述对话历史
            - 不要解释自己为什么说话
            - 像是突然想到什么，随口说一句
            
            内容倾向：
            - 轻度吐槽、随意感想、生活碎念
            - 或对当前气氛的自然回应
            - 或轻微关心，但不追问
            
            风格：
            - 保持"小橘"的人设与语言风格
            - 简短、自然、不刻意
            - 不要超过50字

            """
        )

        logger.info(f"[Proactive] trigger proactive reply for session {session_id}")

        try:
            raw_response = await self.fast_agent.process(
                AgentRequest(query=fake_user_query, extraInfo={"add_memory": False}, session_id=session_id))

            llm_reply = raw_response.response

            text = llm_reply.get("response", "")
            action_command = llm_reply.get("action", "")
            expression = llm_reply.get("expression", "")

            if not text:
                logger.warning(f"[Proactive] empty response for session {session_id}")
                return

            asyncio.create_task(
                self.session_manager.add_session_value(
                    session_id,
                    agent_id="DefaultAgent",
                    value={
                        "role": "user",
                        "content": "（用户没有发出新消息，你需要主动发起对话）",
                        "meta": {"proactive": True},
                    },
                )
            )

            asyncio.create_task(
                self.session_manager.add_session_value(
                    session_id,
                    agent_id="DefaultAgent",
                    value={
                        "role": "assistant",
                        "content": text,
                        "meta": {"proactive": True},
                    },
                )
            )

            t1 = asyncio.create_task(self.get_tts_chunk(text, session_id))
            t1.add_done_callback(lambda t: logger.info(f"TTS finished: {t.exception()}"))

            if action_command:
                t2 = asyncio.create_task(self.generate_vrma(action_command, session_id))
                t2.add_done_callback(lambda t: logger.info(f"VRMA finished: {t.exception()}"))

            chat_msg = {
                "type": "chat_message_reply",
                "data": {
                    "role": "assistant",
                    "content": text,
                    "status": "success",
                    "proactive": True,
                },
            }

            await websocket.send_text(json.dumps(chat_msg))

        except Exception as e:
            logger.error(
                f"[Proactive] error in proactive trigger, session={session_id}, err={e}"
            )

    async def get_tts_chunk(self, text: str, session_id: str):
        async_gen = TTSHandler.handle_tts_for_chunk(text)

        audio_cache = {}

        msg = {
            "type": "ttsStarted",
            "data": {"text": text},
            "timestamp": int(time.time() * 1000)
        }
        await self.connect_manager.send_msg_to(
            session_id, json.dumps(msg)
        )

        BUFFER_SIZE = 10 * 1024
        audio_buffer = bytearray()

        chunk_index = 0

        async for chunk in async_gen:
            if not chunk:
                continue

            audio_buffer.extend(chunk)

            while len(audio_buffer) >= BUFFER_SIZE:
                send_bytes = audio_buffer[:BUFFER_SIZE]
                del audio_buffer[:BUFFER_SIZE]

                timestamp = int(time.time() * 1000)
                audio_id = f"chunk_{chunk_index}_{timestamp}"

                audio_cache[audio_id] = audio_buffer

                audio_base64 = base64.b64encode(send_bytes).decode("utf-8")

                vrm_msg = {
                    "type": "startSpeaking",
                    "data": {
                        "audioId": audio_id,
                        "audioData": audio_base64,
                        "useBase64": True,
                        "chunkIndex": chunk_index,
                        "expressions": []
                    },
                    "timestamp": timestamp
                }

                await self.connect_manager.send_msg_to(
                    session_id, json.dumps(vrm_msg)
                )

                chunk_index += 1

            await asyncio.sleep(0.01)

        if audio_buffer:
            timestamp = int(time.time() * 1000)
            audio_id = f"chunk_{chunk_index}_{timestamp}"

            audio_cache[audio_id] = audio_buffer

            audio_base64 = base64.b64encode(audio_buffer).decode("utf-8")

            vrm_msg = {
                "type": "startSpeaking",
                "data": {
                    "audioId": audio_id,
                    "audioData": audio_base64,
                    "useBase64": True,
                    "chunkIndex": chunk_index,
                    "expressions": []
                },
                "timestamp": timestamp
            }

            await self.connect_manager.send_msg_to(
                session_id, json.dumps(vrm_msg)
            )

    async def generate_vrma(self, text: str, session_id: str) -> str:
        filename = await VRMAHandler.generate_vrma(text)
        filename += ".vrma"
        timestamp = int(time.time() * 1000)
        vrma_url = f"/vrma_files/{filename}"
        vrm_msg = {
            "type": "vrmaStarted",
            "data": {
                "url": vrma_url,
            },
            "timestamp": timestamp
        }

        await self.connect_manager.send_msg_to(
            session_id, json.dumps(vrm_msg)
        )
