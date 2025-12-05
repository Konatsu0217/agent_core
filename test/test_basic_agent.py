import asyncio

from core.fast_agent import FastAgent
from models.agent_data_models import AgentRequest

async def main(mock_input: str):
    await fast_agent.initialize()

    request = AgentRequest(
        query=mock_input
    )

    response = await fast_agent.process(
        request
    )

    print(f"\nresponse: {response}")

if __name__ == "__main__":
    fast_agent = FastAgent()
    asyncio.run(main("你可以有哪些动作"))
