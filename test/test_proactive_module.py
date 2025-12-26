import time
import random
import asyncio
from dataclasses import dataclass
from typing import Dict, Optional, List


@dataclass
class ProactiveState:
    last_query_ts: float
    proactive_weight: float = 0.0
    last_proactive_ts: float = 0.0


class DemoProactiveModule:
    def __init__(
        self,
        check_interval: int = 10,
        weight_inc: float = 1.0,
        threshold: float = 12.0,
        min_proactive_interval: int = 60,
    ):
        # session_id -> ProactiveState
        self.states: Dict[str, ProactiveState] = {}

        self.check_interval = check_interval
        self.weight_inc = weight_inc
        self.threshold = threshold
        self.min_proactive_interval = min_proactive_interval

        self._lock = asyncio.Lock()

    # ----------------------------
    # session 生命周期相关
    # ----------------------------

    async def register_session(self, session_id: str):
        async with self._lock:
            if session_id not in self.states:
                self.states[session_id] = ProactiveState(
                    last_query_ts=time.time()
                )

    async def unregister_session(self, session_id: str):
        async with self._lock:
            self.states.pop(session_id, None)

    async def touch(self, session_id: str):
        """
        在收到用户 query 时调用
        """
        async with self._lock:
            state = self.states.get(session_id)
            if not state:
                self.states[session_id] = ProactiveState(
                    last_query_ts=time.time()
                )
                return

            state.last_query_ts = time.time()
            state.proactive_weight = 0.0

    # ----------------------------
    # 核心逻辑
    # ----------------------------

    async def _check_once(self) -> List[str]:
        """
        执行一次扫描
        返回：需要主动触发的 session_id 列表
        """
        now = time.time()
        triggered: List[str] = []

        async with self._lock:
            for session_id, state in self.states.items():
                idle_time = now - state.last_query_ts

                if idle_time < self.check_interval:
                    continue

                # 增加主动权重
                state.proactive_weight += self.weight_inc

                # 防止过于频繁地主动说话
                if now - state.last_proactive_ts < self.min_proactive_interval:
                    continue

                if state.proactive_weight < self.threshold:
                    continue

                # 根据权重计算概率
                prob = min(1.0, (state.proactive_weight / self.threshold) ** 2)
                if random.random() < prob:
                    state.last_proactive_ts = now
                    state.proactive_weight = 0.0
                    triggered.append(session_id)

        return triggered

    async def run(
        self,
        on_trigger,
    ):
        """
        后台协程入口

        on_trigger: async function(session_id: str)
        """
        while True:
            try:
                triggered_sessions = await self._check_once()
                for session_id in triggered_sessions:
                    await on_trigger(session_id)
            except Exception as e:
                # 这里不要让调度器死掉
                print(f"[ProactiveModule] error: {e}")

            await asyncio.sleep(self.check_interval)
