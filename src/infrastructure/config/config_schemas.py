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


class CoreConfig(BaseModel):
    server: ServerConfig
    backbone_llm_config: BackboneLLMConfig
    pe_config: SimpleURLConfig
    rag_config: SimpleURLConfig
    mcphub_config: MCPHubConfig
