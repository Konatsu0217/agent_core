from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class ServerConfig(BaseModel):
    port: int = Field(default=38888, ge=1, le=65535)
    workers: int = Field(default=1, ge=1)
    limit_concurrency: int = Field(default=50, ge=1)
    backlog: int = Field(default=1024, ge=1)
    reload: bool = False
    timeout_keep_alive: int = Field(default=5, ge=1)


class BackboneLLMConfig(BaseModel):
    openapi_url: str = "https://api.openai.com/v1"
    openapi_key: Optional[str] = ""
    model_name: str = "tts-1"
    temperature: float = 0.7
    max_tokens: int = 1024


class SimpleURLConfig(BaseModel):
    url: str


class MCPHubConfig(BaseModel):
    url: str = "http://127.0.0.1"
    port: int = 9000




class BiliLiveConfig(BaseModel):
    """B站直播客户端配置"""
    id_code: str = Field(default="", description="主播身份码")
    app_id: int = Field(default=0, description="应用ID")
    key: str = Field(default="", description="access_key")
    secret: str = Field(default="", description="access_key_secret")
    host: str = Field(default="https://live-open.biliapi.com", description="开放平台地址")


class DanmakuConfig(BaseModel):
    """弹幕桥接配置"""
    enabled: bool = Field(default=False, description="是否启用弹幕桥接")
    agent_id: str = Field(default="fast_agent_v1", description="弹幕消息使用的 agent ID")
    bucket_capacity: int = Field(default=20, ge=1, description="每个桶最大弹幕数")
    bucket_lifetime: float = Field(default=8.0, gt=0, description="桶的生命周期(秒)")
    bili_live: Optional[BiliLiveConfig] = Field(default=None, description="B站直播客户端配置(可选)")

class CoreConfig(BaseModel):
    server: ServerConfig
    backbone_llm_config: BackboneLLMConfig
    pe_config: SimpleURLConfig
    rag_config: SimpleURLConfig
    mcphub_config: MCPHubConfig
    danmaku_config: Optional[DanmakuConfig] = Field(default=None, description="弹幕桥接配置(可选)")
