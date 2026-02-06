import argparse
import asyncio
import json
import time
import uuid
import websockets
from typing import Optional, List


def build_envelope(event_type: str, session_id: str, payload: dict) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "session_id": session_id,
        "type": event_type,
        "ts": time.time(),
        "source": "client",
        "payload": payload,
        "version": "1.0",
    }


async def connect_once(url: str, origin: Optional[str], text: Optional[str], timeout: float):
    async with websockets.connect(url, origin=origin) as websocket:
        session_id = f"s_{uuid.uuid4().hex}"
        init_payload = {
            "user_id": "debug_user",
            "agent_id": "default",
            "metadata": {},
            "plugin_config": {},
        }
        await websocket.send(
            json.dumps(build_envelope("init_session", session_id, init_payload))
        )
        if text:
            user_payload = {
                "text": text,
                "session_id": session_id,
                "attachments": [],
                "metadata": {},
            }
            await websocket.send(
                json.dumps(build_envelope("user_message", session_id, user_payload))
            )
        try:
            message = await asyncio.wait_for(websocket.recv(), timeout=timeout)
        except asyncio.TimeoutError:
            message = None
        return session_id, message


async def run_all(urls: List[str], origin: Optional[str], text: Optional[str], timeout: float):
    for url in urls:
        print(json.dumps({"action": "connect", "url": url}, ensure_ascii=False))
        try:
            session_id, message = await connect_once(url, origin, text, timeout)
            print(
                json.dumps(
                    {
                        "action": "connected",
                        "url": url,
                        "session_id": session_id,
                        "message": message,
                    },
                    ensure_ascii=False,
                )
            )
        except Exception as exc:
            print(
                json.dumps(
                    {"action": "failed", "url": url, "error": str(exc)},
                    ensure_ascii=False,
                )
            )


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=None)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=38888)
    parser.add_argument("--paths", nargs="*", default=None)
    parser.add_argument("--origin", default=None)
    parser.add_argument("--text", default=None)
    parser.add_argument("--timeout", type=float, default=5.0)
    return parser.parse_args()


def main():
    args = parse_args()
    if args.url:
        urls = [args.url]
    else:
        paths = args.paths or ["/ws/agent"]
        urls = [f"ws://{args.host}:{args.port}{path}" for path in paths]
    asyncio.run(run_all(urls, args.origin, args.text, args.timeout))


if __name__ == "__main__":
    main()
