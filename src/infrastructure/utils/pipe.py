import asyncio
from typing import Any, AsyncIterator, Dict, TypedDict, Literal


class AgentEvent(TypedDict):
    type: Literal["text_delta", "tool_call", "tool_result", "final", "error", "approval_required"]
    payload: Dict[str, Any]


class ProcessPipe:
    def __init__(self):
        self._queue: asyncio.Queue[AgentEvent] = asyncio.Queue()
        loop = asyncio.get_event_loop()
        self._final: asyncio.Future[str] = loop.create_future()

    @property
    def final(self) -> asyncio.Future[str]:
        return self._final

    async def write(self, event: AgentEvent) -> None:
        await self._queue.put(event)
        if event["type"] == "final":
            text = event["payload"].get("text", "")
            if not self._final.done():
                self._final.set_result(text)

    async def reader(self) -> AsyncIterator[AgentEvent]:
        while True:
            event = await self._queue.get()
            yield event
            if event["type"] == "final":
                break

    async def text_delta(self, text: str) -> None:
        await self.write({"type": "text_delta", "payload": {"text": text}})

    async def tool_call(self, name: str, arguments: Any) -> None:
        await self.write({"type": "tool_call", "payload": {"name": name, "arguments": arguments}})

    async def tool_result(self, name: str, success: bool, result: Any) -> None:
        await self.write({"type": "tool_result", "payload": {"name": name, "success": success, "result": result}})

    async def approval_required(self, name: str, arguments: Any, approval_id: str, message: str = "", safety_assessment: Dict[str, Any] | None = None) -> None:
        await self.write({
            "type": "approval_required",
            "payload": {
                "name": name,
                "arguments": arguments,
                "approval_id": approval_id,
                "message": message,
                "safety_assessment": safety_assessment or {}
            }
        })

    async def final_text(self, text: str) -> None:
        await self.write({"type": "final", "payload": {"text": text}})

    async def error(self, message: str) -> None:
        await self.write({"type": "error", "payload": {"message": message}})
