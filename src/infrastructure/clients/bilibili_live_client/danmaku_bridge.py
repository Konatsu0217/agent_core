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
  5. 冷场兜底：连续 idle_timeout 秒无弹幕时，主播主动发起话题
  6. B站热榜注入：冷场时从热门视频中选取与近期聊天相关的视频引导话题

架构位置：
  bilibili_live_client (WS) ──┐
                               ├──► DanmakuBridge ──► Orchestrator ──► LLM
  HTTP /api/danmaku/push ─────┘         │                                │
                                         │         ◄─── _send_event ◄────┘
                                         │
                                    broadcast to all WS clients

  BiliHotFetcher (定时刷新) ──► hot_videos ──► _idle_with_hot_topic()
"""

import asyncio
import logging
import time
import uuid
import dataclasses
from collections import deque
from datetime import datetime
from typing import Dict, Any, List, Optional, TYPE_CHECKING

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

    def is_empty(self) -> bool:
        """两个桶是否都没有待消费的弹幕"""
        return (not self._bucket_a['danmakus']) and (not self._bucket_b['danmakus'])


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
      5. 冷场兜底：idle_timeout 秒无消息时主动发起话题
      6. 热点注入：从 B站热榜选取视频引导话题讨论
    """

    def __init__(
        self,
        agent_id: str = 'fast_agent_v1',
        bucket_capacity: int = 20,
        bucket_lifetime: float = 8.0,
        idle_timeout: float = 30.0,
        broadcast_session_id: str = "danmaku_broadcast_1c31f6ad",
        hot_topic_interval: float = 600.0,
    ):
        self.agent_id = agent_id
        self.bucket = DualBucket(capacity=bucket_capacity, lifetime=bucket_lifetime)
        self.paid_queue = PaidQueue()

        self._orchestrator: Optional['SessionOrchestrator'] = None
        self._running = False
        self._consume_task: Optional[asyncio.Task] = None

        # 弹幕模式下使用一个固定的 broadcast session
        self._broadcast_session_id = broadcast_session_id

        # LLM 是否正在工作（用于消费控制）
        self._is_llm_working = False

        # ---- 冷场兜底 ----
        self._idle_timeout = idle_timeout           # 冷场阈值（秒）
        self._last_activity_time = time.time()      # 上次有弹幕/LLM 完成的时间
        self._idle_triggered = False                 # 本轮冷场是否已触发过话题

        # ---- 热点注入 ----
        self._hot_topic_interval = hot_topic_interval  # 热点话题最小间隔（秒）
        self._last_hot_topic_time: float = 0            # 上次热点话题发送时间
        self._hot_fetcher = None                         # BiliHotFetcher 实例（启动时绑定）

        # ---- 近期聊天上下文（用于热点关联）----
        self._recent_topics: deque = deque(maxlen=50)    # 近 50 条弹幕内容

    def bind_orchestrator(self, orchestrator: 'SessionOrchestrator'):
        """绑定 Orchestrator 实例（在 app startup 时调用）"""
        self._orchestrator = orchestrator
        logger.info(f"[danmaku] bridge bound to orchestrator, agent_id={self.agent_id}")

    def bind_hot_fetcher(self, fetcher):
        """绑定 BiliHotFetcher 实例"""
        self._hot_fetcher = fetcher
        logger.info("[danmaku] bridge bound to hot_fetcher")

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

        # 重置冷场计时
        self._last_activity_time = time.time()
        self._idle_triggered = False

        # 记录到近期话题上下文
        self._recent_topics.append(content)

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
        idle_seconds = time.time() - self._last_activity_time
        return {
            'can_consume': self.can_consume,
            'is_llm_working': self._is_llm_working,
            'pending_paid': self.paid_queue.has_messages(),
            'broadcast_session': self._broadcast_session_id,
            'idle_seconds': round(idle_seconds, 1),
            'idle_triggered': self._idle_triggered,
        }

    # ---- 后台消费循环 ----

    async def start(self):
        """启动弹幕消费后台任务"""
        if self._running:
            return
        self._running = True
        self._last_activity_time = time.time()
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
                # ① 优先处理付费消息
                paid = self.paid_queue.pop()
                if paid:
                    uname = paid.get('uname', '匿名')
                    dtype = paid.get('danmu_type', 'super_chat')
                    content = paid.get('content', '')

                    type_label = {
                        'super_chat': 'SuperChat',
                        'gift': '礼物',
                        'buy_guard': '舰长'
                    }.get(dtype, dtype)
                    query = f"[{type_label}] {uname}: {content}"

                    await self._send_to_llm(query, priority='high')
                    await asyncio.sleep(0.5)
                    continue

                # ② 检查是否可以消费普通弹幕
                if not self.can_consume:
                    await asyncio.sleep(1.0)
                    continue

                # ③ 检查双桶是否有到期的弹幕
                consumable = self.bucket.get_consumable()
                if consumable:
                    merged_text = self.bucket.merge_and_consume(consumable)
                    if merged_text:
                        query = (
                            f"以下是直播间观众发来的弹幕消息，请综合回复：\n"
                            f"---\n"
                            f"{merged_text}\n"
                            f"---"
                        )
                        await self._send_to_llm(query, priority='normal')
                    # 消费完弹幕也重置冷场计时
                    self._last_activity_time = time.time()
                    self._idle_triggered = False
                    await asyncio.sleep(0.5)
                    continue

                # ④ 冷场兜底检查
                idle_seconds = time.time() - self._last_activity_time
                if (idle_seconds >= self._idle_timeout
                        and not self._idle_triggered
                        and self.can_consume
                        and self.bucket.is_empty()
                        and not self.paid_queue.has_messages()):
                    await self._handle_idle()

                tick += 1
                if tick % 20 == 0:
                    a_count = len(self.bucket._bucket_a['danmakus'])
                    b_count = len(self.bucket._bucket_b['danmakus'])
                    logger.debug(
                        f"[danmaku] heartbeat: tick={tick} llm_working={self._is_llm_working} "
                        f"bucket_a={a_count} bucket_b={b_count} "
                        f"idle={idle_seconds:.0f}s idle_triggered={self._idle_triggered}"
                    )
                await asyncio.sleep(0.5)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"[danmaku] consume loop error: {e}")
                await asyncio.sleep(2.0)

    # ---- 冷场兜底 ----

    async def _handle_idle(self):
        """处理冷场：尝试热点话题注入，fallback 到普通主动话题"""
        self._idle_triggered = True
        now = time.time()

        # 检查是否可以做热点注入（有 fetcher 且间隔足够）
        if (self._hot_fetcher
                and now - self._last_hot_topic_time >= self._hot_topic_interval):
            query = self._build_hot_topic_query()
            if query:
                logger.info("[danmaku] idle → hot topic injection")
                self._last_hot_topic_time = now
                await self._send_to_llm(query, priority='idle_hot')
                self._last_activity_time = time.time()
                return

        # fallback: 普通冷场兜底
        logger.info("[danmaku] idle → fallback monologue")
        query = self._build_idle_monologue_query()
        await self._send_to_llm(query, priority='idle')
        self._last_activity_time = time.time()

    def _build_hot_topic_query(self) -> Optional[str]:
        """
        构建热点话题 prompt：
        - 提供 5 个候选热门视频
        - 附带近期弹幕上下文
        - 让 LLM 选择 1 个最相关的展开讨论
        """
        if not self._hot_fetcher:
            return None

        candidates = self._hot_fetcher.pick_topic_candidates(count=5)
        if not candidates:
            return None

        # 格式化候选列表
        candidate_lines = []
        for i, v in enumerate(candidates, 1):
            candidate_lines.append(f"{i}. {v.to_brief()}")
            # 简介不为空时附上
            if v.desc:
                candidate_lines.append(f"   简介: {v.desc}")

        candidates_text = '\n'.join(candidate_lines)

        # 近期弹幕上下文
        recent_context = ""
        if self._recent_topics:
            recent_list = list(self._recent_topics)[-10:]  # 最近 10 条
            recent_context = (
                f"\n\n以下是直播间最近的弹幕内容（供你参考关联性）：\n"
                + '\n'.join(f"- {t}" for t in recent_list)
            )

        # 标记已使用
        for v in candidates:
            self._hot_fetcher.mark_used(v.bvid)

        return (
            f"【角色】\n"
            f"你是一个正在B站直播的虚拟主播。你的说话风格参考 hololive / にじさんじ 的杂谈型VTuber：\n"
            f"- 松弛、自然，像深夜跟朋友语音聊天\n"
            f"- 擅长把普通小事讲出微妙的荒诞感\n"
            f"- 偶尔突然严肃地抛出一个奇怪的哲学问题\n"
            f"- 会自言自语、自问自答，然后突然回过神来跟观众说话\n"
            f"- 有轻微的中二气质但不刻意卖萌\n"
            f"\n"
            f"【场景】\n"
            f"直播间暂时没有新弹幕。你需要自然地发起一段闲聊，活跃气氛、留住观众。\n"
            f"不要表现出没人说话好尴尬的焦虑感——你是那种即使没人听也能自己聊得很开心的类型。\n"
            f"\n"
            f"【素材】以下是当前B站热门视频候选列表：\n"
            f"{candidates_text}\n"
            f"\n"
            f"【近期上下文】\n"
            f"{recent_context}\n"
            f"\n"
            f"【任务】\n"
            f"1. 从候选列表中选 1 个你能自然聊起来的话题。\n"
            f"   选题偏好（按优先级）：\n"
            f"   - 能引出一个仔细想想还挺奇怪的日常观察\n"
            f"   - 能延伸到一个轻哲学/思想实验式的提问\n"
            f"   - 与作为VTuber / 作为AI的微妙身份感有关\n"
            f"   - 有生活感，能让人想起自己的某个瞬间\n"
            f"2. 围绕这个话题展开一小段自然的闲聊。\n"
            f"3. 结尾抛出一个互动问题。\n"
            f"\n"
            f"【话题展开手法（请灵活混用，不要每次都用同一种）】\n"
            f"\n"
            f"A. 日常观察の荒诞化\n"
            f"   从一件很普通的事情开始，越说越觉得不对劲，最后得出一个微妙的结论。\n"
            f"   节奏：平淡开场 → 突然卡住 → \"等一下，这样想的话不是很奇怪吗\" → 展开\n"
            f"\n"
            f"B. 突然的思想实验\n"
            f"   毫无预兆地抛出一个假设性问题，假装很认真地分析，\n"
            f"   然后意识到自己跑题了，但还是很在意答案。\n"
            f"   节奏：\"我突然想到一个问题啊\" → 正经分析 → \"……我为什么在想这个\"\n"
            f"\n"
            f"C. 生活小剧场\n"
            f"   讲一个之前发生的小事（可以是编的但要有真实感），\n"
            f"   重点不是事件本身，而是你对这件事产生了某种奇怪的感悟。\n"
            f"   节奏：叙事 → 停顿 → \"所以我就在想……\" → 升华（但升华得歪歪的）\n"
            f"\n"
            f"D. 对观众的温柔碎碎念\n"
            f"   假装不经意地说一些关心观众的话，但用一种别扭的方式表达。\n"
            f"   节奏：\"话说你们……\" → 关心的内容 → 立刻找补\"才、才不是担心你们呢\"\n"
            f"\n"
            f"【互动问题风格（任选其一）】\n"
            f"- 哲学二选一：两个选项都很奇怪但让人忍不住选（\"你们觉得：永远只能吃一种食物 vs 永远不知道下一顿吃什么，选哪个？\"）\n"
            f"- 微妙共鸣征集：问一个说出来有点丢人但其实很多人都这样的事（\"有没有人跟我一样，出门锁了门之后会反复确认好几次……？\"）\n"
            f"- 无厘头假设：一个完全不影响人生但就是想知道大家怎么想的问题（\"如果你的猫其实听得懂你说话但选择无视你，你会怎么做？\"）\n"
            f"- 轻哲学提问：把日常包装成存在主义式的叩问（\"你们有没有突然觉得，'习惯'这个东西其实挺可怕的？\"）\n"
            f"\n"
            f"【硬性要求】\n"
            f"- 只选 1 个话题展开，不要罗列多个视频\n"
            f"- 总字数 80～180 字，保持杂谈节奏\n"
            f"- 用口语，可以有语气词（嘛、啊、欸、嗯……）和省略号表达停顿\n"
            f"- 可以有日语语气词或少量片假名词汇混用，但主体是中文\n"
            f"- 如果近期上下文中有正在讨论的话题，优先自然衔接\n"
            f"- 整段应该像一个人自然说出来的话，有呼吸感，不要像在念稿\n"
            f"\n"
            f"【禁止事项】\n"
            f"- 禁止出现：\"我从热榜上看到\" \"最近有个很火的\" \"给大家分享一个\" 等暴露素材来源的说法\n"
            f"- 禁止使用中文互联网烂梗：\"家人们\" \"绝绝子\" \"yyds\" \"咱就是说\" \"一整个XX住\" \"听我说谢谢你\"\n"
            f"- 禁止使用书面连接词：\"首先\" \"其次\" \"总结一下\" \"综上所述\"\n"
            f"- 禁止以 \"大家好\" \"各位观众\" \"欢迎来到\" 等正式称呼开场\n"
            f"- 禁止使用 Markdown 格式或特殊排版符号\n"
            f"- 禁止编造与候选列表完全无关的虚假信息\n"
            f"- 禁止过度卖萌或刻意使用颜文字\n"
            f"\n【风格示例（仅供参考语气节奏，不要复制内容）】\n"
            f"\n"
            f"示例A（日常观察の荒诞化）：\n"
            f"欸你们有没有想过一个问题啊……就是，超市里那些试吃的阿姨，"
            f"她们每天要说几百遍'来尝一下'对吧。那她们回到家之后，"
            f"会不会在梦里也在说'来尝一下来尝一下'……"
            f"想到这个我就觉得，人类的职业真的很奇妙啊。"
            f"你们有没有做过那种梦——就是梦里在工作的？弹幕告诉我，我想知道我是不是唯一一个。\n"
            f"\n"
            f"示例B（突然的思想实验）：\n"
            f"……嗯，我刚刚在想一件事。就是，如果记忆可以复制的话，"
            f"那'经历'这个东西还有意义吗。比如说你没有去过海边，"
            f"但是有人把去海边的记忆完整地给你了，那你算是去过了吗……"
            f"嘛，突然说这个好像很奇怪。但是真的很在意欸。"
            f"你们觉得呢——算，还是不算？弹幕扣个 1 或 2 吧。\n"
            f"\n"
            f"示例C（生活小剧场 + 温柔碎碎念）：\n"
            f"我今天出门的时候啊，电梯里遇到一个人，我们俩对视了一下，"
            f"然后同时低头看手机。那个瞬间我就在想，"
            f"人和人之间这种微妙的默契到底是怎么形成的啊……"
            f"明明谁都没说话但是大家都知道'现在应该看手机'。"
            f"话说你们今天有没有好好吃饭啊……没吃的赶紧去吃，"
            f"不、不是担心你们，只是饿着肚子看直播注意力会不集中的嘛。\n"
        )

    def _build_idle_monologue_query(self) -> str:
        """构建普通冷场兜底 prompt"""
        recent_context = ""
        if self._recent_topics:
            recent_list = list(self._recent_topics)[-5:]
            recent_context = (
                f"\n\n最近的弹幕内容（供参考）：\n"
                + '\n'.join(f"- {t}" for t in recent_list)
            )

        return (
            f"你是直播间主播，观众暂时没有发弹幕。"
            f"请主动聊一个有趣的话题来活跃气氛。\n"
            f"可以是：讲一个冷知识、分享一件最近有意思的事、吐槽一件搞笑的事、或者抛出一个互动问题。\n"
            f"不要说「大家好像都不说话了」「怎么没人发弹幕」这种尬聊。"
            f"语气自然，就像朋友间聊天一样。\n"
            f"最后抛出一个问题引导观众回复。"
            f"{recent_context}"
        )

    # ---- 发送到 LLM ----

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
    idle_timeout: float = 30.0,
    hot_topic_interval: float = 600.0,
    broadcast_session_id: str = 'danmaku_broadcast_1c31f6ad',
) -> DanmakuBridge:
    """初始化全局 DanmakuBridge 实例（在 app startup 时调用）"""
    global _bridge_instance
    _bridge_instance = DanmakuBridge(
        agent_id=agent_id,
        bucket_capacity=bucket_capacity,
        bucket_lifetime=bucket_lifetime,
        idle_timeout=idle_timeout,
        broadcast_session_id=broadcast_session_id,
        hot_topic_interval=hot_topic_interval,
    )
    return _bridge_instance
