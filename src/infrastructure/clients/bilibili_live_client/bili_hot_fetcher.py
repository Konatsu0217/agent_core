"""
bili_hot_fetcher.py

B站热门视频抓取器 — 定时拉取 B站热门排行榜，缓存供主动话题使用。

API: GET https://api.bilibili.com/x/web-interface/popular?ps=20&pn=1
返回 data.list[] 每项: title, tname(分区), owner.name, desc, bvid, stat{view,danmaku,like}

架构:
  BiliHotFetcher (后台定时刷新)
       │
       └──► hot_videos: List[HotVideo]  ←── DanmakuBridge._idle_topic_with_hot() 消费
"""

import asyncio
import logging
import time
import random
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

# B站热门 API（无需鉴权）
POPULAR_API = "https://api.bilibili.com/x/web-interface/popular"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Referer': 'https://www.bilibili.com',
}


@dataclass
class HotVideo:
    """热门视频摘要"""
    title: str
    tname: str          # 分区名 (游戏、搞笑、美食...)
    owner: str          # UP主名
    desc: str           # 简介
    bvid: str           # BV号
    view: int = 0       # 播放量
    danmaku: int = 0    # 弹幕数
    like: int = 0       # 点赞数

    @classmethod
    def from_api_item(cls, item: dict) -> 'HotVideo':
        stat = item.get('stat', {})
        owner = item.get('owner', {})
        return cls(
            title=item.get('title', ''),
            tname=item.get('tname', ''),
            owner=owner.get('name', ''),
            desc=(item.get('desc', '') or '')[:100],
            bvid=item.get('bvid', ''),
            view=stat.get('view', 0),
            danmaku=stat.get('danmaku', 0),
            like=stat.get('like', 0),
        )

    def to_brief(self) -> str:
        """生成简短描述（供 LLM prompt 使用）"""
        return (
            f"《{self.title}》(UP主: {self.owner}, 分区: {self.tname}, "
            f"{self.view // 10000}万播放, {self.like}点赞)"
        )


class BiliHotFetcher:
    """
    B站热门视频抓取器

    - 后台每 refresh_interval 秒刷新一次热榜
    - 对外暴露 get_hot_videos() 获取当前缓存
    - pick_topic_candidates() 随机选取 N 个候选供 LLM 挑选
    """

    def __init__(self, refresh_interval: float = 600.0, page_size: int = 20):
        """
        Args:
            refresh_interval: 刷新间隔（秒），默认 10 分钟
            page_size: 每次拉取的视频数，默认 20
        """
        self.refresh_interval = refresh_interval
        self.page_size = page_size

        self._hot_videos: List[HotVideo] = []
        self._last_fetch_time: float = 0
        self._running = False
        self._fetch_task: Optional[asyncio.Task] = None
        # 已使用过的 bvid，避免短期内重复推荐
        self._used_bvids: set = set()

    async def start(self):
        """启动后台定时刷新"""
        if self._running:
            return
        self._running = True

        # 启动时立即拉取热门视频，失败重试最多 3 次
        for attempt in range(1, 4):
            await self._fetch_once()
            if self._hot_videos:
                logger.info(
                    f"[hot_fetcher] initial fetch OK: {len(self._hot_videos)} videos "
                    f"(attempt {attempt}), first: {self._hot_videos[0].title}"
                )
                break
            logger.warning(f"[hot_fetcher] initial fetch attempt {attempt}/3 returned empty, retrying in 3s...")
            await asyncio.sleep(3)

        if not self._hot_videos:
            logger.error("[hot_fetcher] initial fetch FAILED after 3 attempts, will retry in background")

        self._fetch_task = asyncio.create_task(self._refresh_loop())
        logger.info(f"[hot_fetcher] started, refresh_interval={self.refresh_interval}s")

    async def stop(self):
        """停止"""
        self._running = False
        if self._fetch_task:
            self._fetch_task.cancel()
            try:
                await self._fetch_task
            except asyncio.CancelledError:
                pass
        logger.info("[hot_fetcher] stopped")

    def get_hot_videos(self) -> List[HotVideo]:
        """获取当前热门视频缓存"""
        return list(self._hot_videos)

    def pick_topic_candidates(self, count: int = 5) -> List[HotVideo]:
        """
        随机选取 count 个未使用过的热门视频作为话题候选。
        如果所有视频都用过了，清空已用记录重新选。
        """
        available = [v for v in self._hot_videos if v.bvid not in self._used_bvids]
        if not available:
            # 全部用过了，重置
            self._used_bvids.clear()
            available = list(self._hot_videos)
        if not available:
            return []

        selected = random.sample(available, min(count, len(available)))
        return selected

    def mark_used(self, bvid: str):
        """标记某个视频已被用于话题，短期内不再推荐"""
        self._used_bvids.add(bvid)

    # ---- 内部 ----

    async def _refresh_loop(self):
        """后台定时刷新循环"""
        while self._running:
            try:
                await asyncio.sleep(self.refresh_interval)
                await self._fetch_once()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"[hot_fetcher] refresh error: {e}")
                await asyncio.sleep(30)

    async def _fetch_once(self):
        """拉取一次 B站热门视频列表"""
        import aiohttp
        import ssl

        params = {'ps': self.page_size, 'pn': 1}
        try:
            # 兼容 macOS Python 缺少根证书的情况
            ssl_ctx = ssl.create_default_context()
            try:
                import certifi
                ssl_ctx.load_verify_locations(certifi.where())
            except ImportError:
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE

            connector = aiohttp.TCPConnector(ssl=ssl_ctx)
            async with aiohttp.ClientSession(connector=connector, headers=HEADERS) as session:
                async with session.get(POPULAR_API, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        logger.warning(f"[hot_fetcher] API returned status {resp.status}")
                        return
                    data = await resp.json()

            if data.get('code') != 0:
                logger.warning(f"[hot_fetcher] API error: code={data.get('code')} msg={data.get('message')}")
                return

            video_list = data.get('data', {}).get('list', [])
            self._hot_videos = [HotVideo.from_api_item(item) for item in video_list]
            self._last_fetch_time = time.time()
            logger.info(f"[hot_fetcher] fetched {len(self._hot_videos)} hot videos")

        except Exception as e:
            logger.exception(f"[hot_fetcher] fetch failed: {e}")


# ======================== 全局单例 ========================

_fetcher_instance: Optional[BiliHotFetcher] = None


def get_hot_fetcher() -> BiliHotFetcher:
    global _fetcher_instance
    if _fetcher_instance is None:
        _fetcher_instance = BiliHotFetcher()
    return _fetcher_instance


def init_hot_fetcher(refresh_interval: float = 600.0, page_size: int = 20) -> BiliHotFetcher:
    global _fetcher_instance
    _fetcher_instance = BiliHotFetcher(
        refresh_interval=refresh_interval,
        page_size=page_size,
    )
    return _fetcher_instance
