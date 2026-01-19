# 新增：接收弹幕代理服务发送的弹幕消息
from typing import Optional

from pydantic import BaseModel, Field


class DanmakuData(BaseModel):
    type: str = Field(..., description="消息类型")
    content: str = Field(..., description="弹幕内容")
    danmu_type: str = Field(..., description="弹幕类型")
    timestamp: Optional[str] = Field(None, description="时间戳")
    count: Optional[int] = Field(1, description="弹幕数量")