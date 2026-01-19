import uuid
from typing import Any

from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    query: str
    extraInfo: dict = Field(default_factory=dict)
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

class AgentResponse(BaseModel):
    response: dict
    session_id: str
