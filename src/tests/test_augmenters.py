import asyncio
import os
import sys
from typing import Dict, Any

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from src.context.context_maker import DefaultContextMaker
from src.context.augmenters import REGISTRY


class FakePromptService:
    async def build_prompt(self, session_id: str, agent_profile: Dict[str, Any], **kwargs) -> str:
        return "BASE_PROMPT"


async def run_test():
    agent_profile = {
        "name": "test_agent",
        "agent_type": "combined",
        "prompt_config": {},
        "augmenters": [
            {"name": "append_text", "params": {"text": "APPEND_TEXT"}},
            {"name": "time_augmenter"}
        ]
    }

    cm = DefaultContextMaker(prompt_service=FakePromptService())
    cm.agent_profile = agent_profile

    ctx = await cm.build_context("sid", "hello")

    base_ok = "BASE_PROMPT" in ctx.system_prompt
    append_ok = "APPEND_TEXT" in ctx.system_prompt
    print("REGISTRY:", list(REGISTRY.keys()))
    print(ctx.system_prompt)
    if base_ok and append_ok:
        print("OK")
    else:
        print("FAIL")


if __name__ == "__main__":
    asyncio.run(run_test())
