import asyncio

from src.agent.fast_agent import FastAgent
from src.infrastructure.handlers.tts_handler import TTSHandler
from src.infrastructure.handlers.vrma_handler import VRMAHandler
from src.domain.models.agent_data_models import AgentRequest

async def main(mock_input: str):
    await fast_agent.initialize()

    request = AgentRequest(
        query=mock_input
    )

    response = await fast_agent.process(
        request
    )

    text = response.response.get('response', '')
    motion_prompt = response.response.get('action', '')

    print(f"\nresponse: {response}")


    print(f"text: {text}")

    tts_task = asyncio.create_task(TTSHandler.handle_tts_direct_play(text))
    vrma_task = asyncio.create_task(VRMAHandler.generate_vrma(motion_prompt))
    await asyncio.gather(tts_task, vrma_task)

if __name__ == "__main__":
    fast_agent = FastAgent(use_tools=False)
    asyncio.run(main("你可以有哪些动作"))
