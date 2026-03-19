"""
danmaku_bridge.py

弹幕桥接模块 — 将 B站直播弹幕聚合后作为 query 发送给 LLM，响应广播到所有 WS 客户端。

核心逻辑：
  1. 接收弹幕消息（来自 B站直播客户端回调 或 HTTP /api/danmaku/push 接口）
  2. 双桶聚合算法（移植自 danmaku_proxy_server）：
     - 普通弹幕进 A/B 双桶，桶满或超时后合并成一条聚合消息
     - 付费消息（SC/礼物/舰长）走优先队列，直接发送不等待聚合
  3. 聚合后的弹幕作为 user_message 送入 SessionOrchestrator.handle_user_message
  4. LLM 响应通过 WebSocketManager 广播到所有连接的客户端

架构位置：
  bilibili_live_client (WS) ──┐
                               ├──► DanmakuBridge ──► Orchestrator ──► LLM
  HTTP /api/danmaku/push ─────┘         │                                │
                                         │         ◄─── _send_event ◄────┘
                                         │
                                    broadcast to all WS clients
"""

import asyncio
import logging
import time
import uuid
import dataclasses
from collections import deque
from datetime import datetime
from typing import Dict, Any, Optional, TYPE_CHECKING

from src.domain.events import (
    ClientEventEnvelope, ClientEventType, ClientEventPayload,
    UserMessagePayload, ServerEventType, ServiceEventEnvelope,
    StatePayload
)
from src.infrastructure.utils.connet_manager import get_ws_manager

if TYPE_CHECKING:
    from src.main.session_orchestrator import SessionOrchestrator

logger = logging.getLogger(__name__)


# ======================== 双桶聚合算法（移植自 danmaku_proxy_server） ========================

class DualBucket:
    """双桶缓冲系统 — A/B 桶交替收集弹幕，到期后合并输出"""

    def __init__(self, capacity: int = 20, lifetime: float = 8.0):
        """
        Args:
            capacity: 每个桶最大弹幕数（超出自动丢弃最早的）
            lifetime: 桶的生命周期（秒），超时后触发消费
        """
        self.capacity = capacity
        self.lifetime = lifetime

        self._bucket_a = self._new_bucket(active=True)
        self._bucket_b = self._new_bucket(active=False)
        self._current = self._bucket_a

    def _new_bucket(self, active: bool = False) -> Dict[str, Any]:
        return {
            'danmakus': deque(maxlen=self.capacity),
            'start_time': time.time() if active else None,
            'is_active': active,
            'is_consuming': False,
        }

    def add(self, content: str, danmu_type: str = 'danmaku', uname: str = ''):
        """添加一条弹幕到当前活跃桶"""
        # 如果当前桶正在消费，切换到另一个桶
        if self._current['is_consuming']:
            other = self._bucket_b if self._current is self._bucket_a else self._bucket_a
            if not other['is_active']:
                other['is_active'] = True
                other['start_time'] = time.time()
                other['danmakus'].clear()
            self._current = other

        self._current['danmakus'].append({
            'content': content,
            'uname': uname,
            'danmu_type': danmu_type,
            'ts': time.time(),
        })

    def get_consumable(self) -> Optional[Dict]:
        """获取已到期且有内容的桶"""
        now = time.time()
        for bucket in (self._bucket_a, self._bucket_b):
            if (bucket['is_active']
                    and not bucket['is_consuming']
                    and bucket['danmakus']
                    and bucket['start_time'] is not None
                    and now - bucket['start_time'] > self.lifetime):
                return bucket
        return None

    def merge_and_consume(self, bucket: Dict) -> Optional[str]:
        """合并桶内弹幕并标记消费，返回合并后的文本"""
        bucket['is_consuming'] = True
        if not bucket['danmakus']:
            self._switch(bucket)
            return None

        # 格式化弹幕：每条一行，带用户名
        lines = []
        for dm in bucket['danmakus']:
            uname = dm.get('uname', '匿名')
            content = dm.get('content', '')
            lines.append(f"{uname}: {content}")

        merged = '\n'.join(lines)
        count = len(bucket['danmakus'])
        self._switch(bucket)
        logger.info(f"[danmaku] merged {count} messages into query ({len(merged)} chars)")
        return merged

    def _switch(self, consumed_bucket: Dict):
        """切换桶：清理已消费的桶，激活另一个"""
        consumed_bucket['is_active'] = False
        consumed_bucket['is_consuming'] = False
        consumed_bucket['danmakus'].clear()
        consumed_bucket['start_time'] = None

        other = self._bucket_b if consumed_bucket is self._bucket_a else self._bucket_a
        if not other['is_active']:
            other['is_active'] = True
            other['start_time'] = time.time()
        self._current = other


# ======================== 付费消息优先队列 ========================

class PaidQueue:
    """付费消息队列（SC/礼物/舰长）— 不走聚合，直接发送"""

    PAID_TYPES = {'super_chat', 'gift', 'buy_guard'}

    def __init__(self):
        self._queue: deque = deque()

    @classmethod
    def is_paid(cls, danmu_type: str) -> bool:
        return danmu_type in cls.PAID_TYPES

    def put(self, content: str, danmu_type: str, uname: str = ''):
        self._queue.append({
            'content': content,
            'danmu_type': danmu_type,
            'uname': uname,
            'ts': time.time(),
        })
        logger.info(f"[danmaku] paid message queued: {danmu_type} from {uname}")

    def pop(self) -> Optional[Dict]:
        return self._queue.popleft() if self._queue else None

    def has_messages(self) -> bool:
        return len(self._queue) > 0


# ======================== DanmakuBridge 主控 ========================

class DanmakuBridge:
    """
    弹幕桥接器 — 连接 B站弹幕源 与 agent_core Orchestrator

    职责：
      1. 接收弹幕（push 接口 / B站客户端回调）
      2. 双桶聚合普通弹幕 + 付费消息优先队列
      3. 将聚合文本作为 user_message 送入 Orchestrator
      4. Orchestrator 的 LLM 响应会通过 broadcast 广播到所有 WS 客户端
    """

    def __init__(
        self,
        agent_id: str = 'fast_agent_v1',
        bucket_capacity: int = 20,
        bucket_lifetime: float = 8.0,
    ):
        self.agent_id = agent_id
        self.bucket = DualBucket(capacity=bucket_capacity, lifetime=bucket_lifetime)
        self.paid_queue = PaidQueue()

        self._orchestrator: Optional['SessionOrchestrator'] = None
        self._running = False
        self._consume_task: Optional[asyncio.Task] = None

        # 弹幕模式下使用一个固定的 broadcast session
        self._broadcast_session_id = f"danmaku_broadcast_{uuid.uuid4().hex[:8]}"

        # LLM 是否正在工作（用于消费控制）
        self._is_llm_working = False

    def bind_orchestrator(self, orchestrator: 'SessionOrchestrator'):
        """绑定 Orchestrator 实例（在 app startup 时调用）"""
        self._orchestrator = orchestrator
        logger.info(f"[danmaku] bridge bound to orchestrator, agent_id={self.agent_id}")

    # ---- 弹幕接收入口 ----

    def push_danmaku(self, content: str, danmu_type: str = 'danmaku', uname: str = ''):
        """
        接收一条弹幕消息（同步方法，可在任何地方调用）

        Args:
            content: 弹幕文本
            danmu_type: 弹幕类型 (danmaku / super_chat / gift / buy_guard)
            uname: 发送者用户名
        """
        logger.info(f"[danmaku] push_danmaku: type={danmu_type} uname={uname} content={content[:50]}")
        if PaidQueue.is_paid(danmu_type):
            self.paid_queue.put(content, danmu_type, uname)
        else:
            self.bucket.add(content, danmu_type, uname)

    # ---- 消费控制 ----

    @property
    def can_consume(self) -> bool:
        """检查是否可以消费（LLM 空闲时允许）"""
        return not self._is_llm_working

    def get_consumption_status(self) -> Dict[str, Any]:
        """返回消费状态（供 /api/consumption-status 接口使用）"""
        return {
            'can_consume': self.can_consume,
            'is_llm_working': self._is_llm_working,
            'pending_paid': self.paid_queue.has_messages(),
            'broadcast_session': self._broadcast_session_id,
        }

    # ---- 后台消费循环 ----

    async def start(self):
        """启动弹幕消费后台任务"""
        if self._running:
            return
        self._running = True
        self._consume_task = asyncio.create_task(self._consume_loop())
        logger.info(f"[danmaku] bridge started, broadcast_session={self._broadcast_session_id}")

    async def stop(self):
        """停止消费"""
        self._running = False
        if self._consume_task:
            self._consume_task.cancel()
            try:
                await self._consume_task
            except asyncio.CancelledError:
                pass
        logger.info("[danmaku] bridge stopped")

    async def _consume_loop(self):
        """主消费循环"""
        logger.info(f"[danmaku] consume_loop started, agent_id={self.agent_id}, session={self._broadcast_session_id}")
        tick = 0
        while self._running:
            try:
                # 优先处理付费消息
                paid = self.paid_queue.pop()
                if paid:
                    uname = paid.get('uname', '匿名')
                    dtype = paid.get('danmu_type', 'super_chat')
                    content = paid.get('content', '')

                    # 格式化付费消息 query
                    type_label = {
                        'super_chat': 'SuperChat',
                        'gift': '礼物',
                        'buy_guard': '舰长'
                    }.get(dtype, dtype)
                    query = f"[{type_label}] {uname}: {content}"

                    await self._send_to_llm(query, priority='high')
                    await asyncio.sleep(0.5)
                    continue

                # 检查是否可以消费普通弹幕
                if not self.can_consume:
                    await asyncio.sleep(1.0)
                    continue

                # 检查双桶是否有到期的弹幕
                consumable = self.bucket.get_consumable()
                if consumable:
                    merged_text = self.bucket.merge_and_consume(consumable)
                    if merged_text:
                        # 构建聚合 query（带上下文提示）
                        query = (
                            f"以下是直播间观众发来的弹幕消息，请综合回复：\n"
                            f"---\n"
                            f"{merged_text}\n"
                            f"---"
                        )
                        await self._send_to_llm(query, priority='normal')

                tick += 1
                if tick % 20 == 0:
                    a_count = len(self.bucket._bucket_a['danmakus'])
                    b_count = len(self.bucket._bucket_b['danmakus'])
                    logger.debug(f"[danmaku] heartbeat: tick={tick} llm_working={self._is_llm_working} bucket_a={a_count} bucket_b={b_count} paid={self.paid_queue.has_messages()}")
                await asyncio.sleep(0.5)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"[danmaku] consume loop error: {e}")
                await asyncio.sleep(2.0)

    async def _send_to_llm(self, query: str, priority: str = 'normal'):
        """将聚合弹幕作为 user_message 送入 Orchestrator，响应广播到所有客户端"""
        if not self._orchestrator:
            logger.warning("[danmaku] orchestrator not bound, dropping message")
            return

        self._is_llm_working = True
        session_id = self._broadcast_session_id

        try:
            logger.info(
                f"[danmaku] sending to LLM: priority={priority} "
                f"session_id={session_id} query_len={len(query)}"
            )

            # 构建 UserMessagePayload
            payload = UserMessagePayload(
                text=query,
                session_id=session_id,
                metadata={'source': 'danmaku', 'priority': priority}
            )

            # 调用 orchestrator 处理用户消息
            await self._orchestrator.handle_user_message(
                session_id=session_id,
                agent_id=self.agent_id,
                payload=payload,
            )

            logger.info(f"[danmaku] LLM request completed: session_id={session_id}")

        except Exception as e:
            logger.exception(f"[danmaku] LLM request failed: {e}")

        finally:
            self._is_llm_working = False

    async def _broadcast_to_all_clients(self, session_id: str, envelope: ServiceEventEnvelope):
        """将事件广播到所有 WS 客户端（不仅仅是当前 session）"""
        ws_manager = get_ws_manager()
        try:
            data = dataclasses.asdict(envelope)
            import json
            msg = json.dumps(data, ensure_ascii=False, default=str)
            await ws_manager.broadcast_websocket(msg, None)
        except Exception as e:
            logger.error(f"[danmaku] broadcast failed: {e}")


# ======================== 全局单例 ========================

_bridge_instance: Optional[DanmakuBridge] = None


def get_danmaku_bridge() -> DanmakuBridge:
    """获取全局 DanmakuBridge 实例"""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = DanmakuBridge()
    return _bridge_instance


def init_danmaku_bridge(
    agent_id: str = 'fast_agent_v1',
    bucket_capacity: int = 20,
    bucket_lifetime: float = 8.0,
) -> DanmakuBridge:
    """初始化全局 DanmakuBridge 实例（在 app startup 时调用）"""
    global _bridge_instance
    _bridge_instance = DanmakuBridge(
        agent_id=agent_id,
        bucket_capacity=bucket_capacity,
        bucket_lifetime=bucket_lifetime,
    )
    return _bridge_instance
