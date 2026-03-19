import struct
import json
import logging

logger = logging.getLogger(__name__)

# 弹幕回调函数（由外部设置）
_danmaku_callback = None


def set_danmaku_callback(callback):
    """设置弹幕回调函数，callback(cmd: str, data: dict)"""
    global _danmaku_callback
    _danmaku_callback = callback
    logger.info("[proto] danmaku callback registered")


class Proto:
    def __init__(self):
        self.packetLen = 0
        self.headerLen = 16
        self.ver = 0
        self.op = 0
        self.seq = 0
        self.body = ''
        self.maxBody = 2048

    def pack(self):
        self.packetLen = len(self.body) + self.headerLen
        buf = struct.pack('>i', self.packetLen)
        buf += struct.pack('>h', self.headerLen)
        buf += struct.pack('>h', self.ver)
        buf += struct.pack('>i', self.op)
        buf += struct.pack('>i', self.seq)
        buf += self.body.encode()
        return buf

    def unpack(self, buf):
        if len(buf) < self.headerLen:
            logger.warning("包头不够")
            return
        self.packetLen = struct.unpack('>i', buf[0:4])[0]
        self.headerLen = struct.unpack('>h', buf[4:6])[0]
        self.ver = struct.unpack('>h', buf[6:8])[0]
        self.op = struct.unpack('>i', buf[8:12])[0]
        self.seq = struct.unpack('>i', buf[12:16])[0]
        if self.packetLen < 0 or self.packetLen > self.maxBody:
            logger.warning(f"包体长不对 self.packetLen: {self.packetLen} self.maxBody: {self.maxBody}")
            return
        bodyLen = self.packetLen - self.headerLen
        self.body = buf[16:self.packetLen]
        if bodyLen <= 0:
            return
        if self.ver == 0:
            # 解析 JSON 消息体
            try:
                body_str = self.body.decode('utf-8') if isinstance(self.body, bytes) else self.body
                body_json = json.loads(body_str)
                cmd = body_json.get('cmd', '')

                # 触发回调
                if _danmaku_callback and cmd:
                    _danmaku_callback(cmd, body_json.get('data', {}))

                logger.debug(f"[proto] received: cmd={cmd}")
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.debug(f"[proto] body parse failed: {e}")
        else:
            return
