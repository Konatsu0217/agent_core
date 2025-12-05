import asyncio

from core.fast_agent import FastAgent
from handlers.tts_handler import TTSHandler
from models.agent_data_models import AgentRequest

async def main(mock_input: str):
    await fast_agent.initialize()

    request = AgentRequest(
        query=mock_input
    )

    response = await fast_agent.process(
        request
    )

    text = response.response.get('response', '')

    print(f"\nresponse: {response}")

    await TTSHandler.handle_tts_direct_play(text)

if __name__ == "__main__":
    fast_agent = FastAgent(use_tools=False)
    asyncio.run(main("你可以有哪些动作"))
