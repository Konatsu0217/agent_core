import asyncio
from typing import Any, AsyncIterator, Dict, TypedDict, Literal


class AgentEvent(TypedDict):
    type: Literal["text_delta", "tool_call", "tool_result", "final", "error", "approval_required", "approval_decision", "think_delta"]
    payload: Dict[str, Any]


class ProcessPipe:
    def __init__(self):
        self._queue: asyncio.Queue[AgentEvent] = asyncio.Queue()
        loop = asyncio.get_event_loop()
        self._final: asyncio.Future[str] = loop.create_future()
        self._approval_waiters: Dict[str, asyncio.Future[str]] = {}
        self._approval_results: Dict[str, str] = {}
        self._closed = False
        self._cancelled = False

    @property
    def final(self) -> asyncio.Future[str]:
        return self._final

    def is_closed(self) -> bool:
        return self._closed

    def is_cancelled(self) -> bool:
        return self._cancelled

    async def write(self, event: AgentEvent) -> None:
        if self._closed:
            return
        await self._queue.put(event)
        if event["type"] == "final":
            text = event["payload"].get("text", "")
            if not self._final.done():
                self._final.set_result(text)
            self._closed = True

    async def reader(self) -> AsyncIterator[AgentEvent]:
        while True:
            event = await self._queue.get()
            yield event
            if event["type"] == "final":
                break

    async def text_delta(self, text: str) -> None:
        await self.write({"type": "text_delta", "payload": {"text": text}})
        
    async def think_delta(self, text: str) -> None:
        await self.write({"type": "think_delta", "payload": {"text": text}})

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

    async def approval_decision(self, approval_id: str, decision: Literal["approved", "rejected"], message: str = "") -> None:
        await self.write({
            "type": "approval_decision",
            "payload": {
                "approval_id": approval_id,
                "decision": decision,
                "message": message,
            }
        })
        fut = self._approval_waiters.get(approval_id)
        if fut and not fut.done():
            fut.set_result(decision)
            self._approval_waiters.pop(approval_id, None)
        else:
            self._approval_results[approval_id] = decision

    async def wait_for_approval(self, approval_id: str, timeout: float | None = None) -> str:
        existing = self._approval_results.pop(approval_id, None)
        if existing:
            return existing
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        self._approval_waiters[approval_id] = fut
        try:
            if timeout is not None:
                decision = await asyncio.wait_for(fut, timeout=timeout)
            else:
                decision = await fut
            return decision
        finally:
            self._approval_waiters.pop(approval_id, None)

    async def final_text(self, text: str) -> None:
        await self.write({"type": "final", "payload": {"text": text}})

    async def error(self, message: str) -> None:
        await self.write({"type": "error", "payload": {"message": message}})

    async def close(self, message: str | None = None) -> None:
        if self._closed:
            return
        if message == "request_cancelled":
            self._cancelled = True
        for approval_id, fut in list(self._approval_waiters.items()):
            if not fut.done():
                fut.set_result("rejected")
            self._approval_waiters.pop(approval_id, None)
        self._approval_results.clear()
        if message:
            await self.error(message)
        if not self._final.done():
            await self.final_text("")
