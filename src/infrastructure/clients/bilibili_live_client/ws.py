import asyncio
import json
import logging
import websockets
import requests
import time
import hashlib
import hmac
import random
from hashlib import sha256

from src.infrastructure.clients.bilibili_live_client import proto
from src.infrastructure.clients.bilibili_live_client.proto import set_danmaku_callback
from src.infrastructure.clients.bilibili_live_client.msgEnum import DANMU_TYPE

logger = logging.getLogger(__name__)


class BiliClient:
    """
    B站直播开放平台 WebSocket 客户端

    监听指定直播间的弹幕消息，通过回调函数将消息转发给 DanmakuBridge。
    """

    def __init__(self, idCode, appId, key, secret, host, on_danmaku=None):
        """
        Args:
            idCode: 主播身份码
            appId: 应用 ID
            key: access_key
            secret: access_key_secret
            host: 开放平台 API 地址
            on_danmaku: 弹幕回调 fn(content, danmu_type, uname)
        """
        self.idCode = idCode
        self.appId = appId
        self.key = key
        self.secret = secret
        self.host = host
        self.gameId = ''
        self._on_danmaku = on_danmaku

        # 注册 proto 层的回调
        set_danmaku_callback(self._handle_proto_message)

    def _handle_proto_message(self, cmd: str, data: dict):
        """处理 proto 层解析出来的消息"""
        if not self._on_danmaku:
            return

        # 弹幕类型映射
        type_map = {
            'LIVE_OPEN_PLATFORM_DM': 'danmaku',
            'LIVE_OPEN_PLATFORM_SUPER_CHAT': 'super_chat',
            'LIVE_OPEN_PLATFORM_SEND_GIFT': 'gift',
            'LIVE_OPEN_PLATFORM_GUARD': 'buy_guard',
        }

        danmu_type = type_map.get(cmd)
        if not danmu_type:
            return

        # 提取消息内容和用户名
        uname = data.get('uname', '匿名')

        if danmu_type == 'danmaku':
            content = data.get('msg', '')
        elif danmu_type == 'super_chat':
            content = data.get('message', '') or data.get('msg', '')
        elif danmu_type == 'gift':
            gift_name = data.get('gift_name', '礼物')
            gift_num = data.get('gift_num', 1)
            content = f"赠送了 {gift_num} 个 {gift_name}"
        elif danmu_type == 'buy_guard':
            guard_level = data.get('guard_level', 0)
            level_name = {1: '总督', 2: '提督', 3: '舰长'}.get(guard_level, '舰长')
            content = f"购买了 {level_name}"
        else:
            content = str(data)

        if content:
            label = DANMU_TYPE.get(cmd, cmd)
            logger.info(f"[bili] {label}: {uname} -> {content[:50]}")
            self._on_danmaku(content, danmu_type, uname)

    # ---- 事件循环 ----

    def run(self):
        """同步入口，在独立线程中创建新的事件循环运行"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            websocket = loop.run_until_complete(self.connect())
            tasks = [
                asyncio.ensure_future(self.recvLoop(websocket)),
                asyncio.ensure_future(self.heartBeat(websocket)),
                asyncio.ensure_future(self.appheartBeat()),
            ]
            loop.run_until_complete(asyncio.gather(*tasks))
        except Exception as e:
            logger.exception(f"[bili] event loop error: {e}")
        finally:
            loop.close()

    async def run_async(self):
        """异步版本的 run，可在 asyncio 环境中使用"""
        websocket = await self.connect()
        await asyncio.gather(
            self.recvLoop(websocket),
            self.heartBeat(websocket),
            self.appheartBeat(),
        )

    # ---- HTTP 签名 ----

    def sign(self, params):
        key = self.key
        secret = self.secret
        md5 = hashlib.md5()
        md5.update(params.encode())
        ts = time.time()
        nonce = random.randint(1, 100000) + time.time()
        md5data = md5.hexdigest()
        headerMap = {
            "x-bili-timestamp": str(int(ts)),
            "x-bili-signature-method": "HMAC-SHA256",
            "x-bili-signature-nonce": str(nonce),
            "x-bili-accesskeyid": key,
            "x-bili-signature-version": "1.0",
            "x-bili-content-md5": md5data,
        }

        headerList = sorted(headerMap)
        headerStr = ''
        for key in headerList:
            headerStr = headerStr + key + ":" + str(headerMap[key]) + "\n"
        headerStr = headerStr.rstrip("\n")

        appsecret = secret.encode()
        data = headerStr.encode()
        signature = hmac.new(appsecret, data, digestmod=sha256).hexdigest()
        headerMap["Authorization"] = signature
        headerMap["Content-Type"] = "application/json"
        headerMap["Accept"] = "application/json"
        return headerMap

    # ---- 获取 WS 连接信息 ----

    def getWebsocketInfo(self):
        postUrl = "%s/v2/app/start" % self.host
        params = '{"code":"%s","app_id":%d}' % (self.idCode, self.appId)
        headerMap = self.sign(params)
        r = requests.post(url=postUrl, headers=headerMap, data=params, verify=False)
        data = json.loads(r.content)
        logger.info(f"[bili] app/start response: {json.dumps(data, ensure_ascii=False)[:200]}")

        self.gameId = str(data['data']['game_info']['game_id'])
        return (
            str(data['data']['websocket_info']['wss_link'][0]),
            str(data['data']['websocket_info']['auth_body'])
        )

    # ---- 应用心跳 ----

    async def appheartBeat(self):
        while True:
            await asyncio.sleep(20)
            postUrl = "%s/v2/app/heartbeat" % self.host
            params = '{"game_id":"%s"}' % self.gameId
            headerMap = self.sign(params)
            try:
                r = requests.post(url=postUrl, headers=headerMap, data=params, verify=False)
                logger.debug("[bili] app heartbeat sent")
            except Exception as e:
                logger.warning(f"[bili] app heartbeat failed: {e}")

    # ---- WS 鉴权 ----

    async def auth(self, websocket, authBody):
        req = proto.Proto()
        req.body = authBody
        req.op = 7
        await websocket.send(req.pack())
        buf = await websocket.recv()
        resp = proto.Proto()
        resp.unpack(buf)
        respBody = json.loads(resp.body)
        if respBody["code"] != 0:
            logger.error("[bili] auth failed")
        else:
            logger.info("[bili] auth success")

    # ---- WS 心跳 ----

    async def heartBeat(self, websocket):
        while True:
            await asyncio.sleep(20)
            req = proto.Proto()
            req.op = 2
            try:
                await websocket.send(req.pack())
                logger.debug("[bili] ws heartbeat sent")
            except Exception as e:
                logger.warning(f"[bili] ws heartbeat failed: {e}")

    # ---- 消息接收循环 ----

    async def recvLoop(self, websocket):
        logger.info("[bili] recv loop started")
        while True:
            try:
                recvBuf = await websocket.recv()
                resp = proto.Proto()
                resp.unpack(recvBuf)
            except websockets.exceptions.ConnectionClosed:
                logger.warning("[bili] ws connection closed, reconnecting...")
                websocket = await self.connect()
            except Exception as e:
                logger.error(f"[bili] recv error: {e}")
                await asyncio.sleep(1)

    # ---- 建立连接 ----

    async def connect(self):
        addr, authBody = self.getWebsocketInfo()
        logger.info(f"[bili] connecting to {addr[:60]}...")
        websocket = await websockets.connect(addr)
        await self.auth(websocket, authBody)
        return websocket

    def __enter__(self):
        logger.info("[bili] enter")

    def __exit__(self, type, value, trace):
        postUrl = "%s/v2/app/end" % self.host
        params = '{"game_id":"%s","app_id":%d}' % (self.gameId, self.appId)
        headerMap = self.sign(params)
        try:
            r = requests.post(url=postUrl, headers=headerMap, data=params, verify=False)
            logger.info(f"[bili] end app success: {params}")
        except Exception as e:
            logger.error(f"[bili] end app failed: {e}")
