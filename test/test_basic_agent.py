import asyncio
import json
from src.agent.agent_factory import AgentFactory
from src.domain.models.agent_data_models import AgentRequest

async def main(mock_input: str):
    agent = await AgentFactory.get_basic_agent()
    await agent.initialize()

    request = AgentRequest(query=mock_input)
    pipe = await agent.process(request)

    collected = []
    async for event in pipe.reader():
        if event["type"] == "text_delta":
            collected.append(event["payload"]["text"])
        elif event["type"] == "tool_call":
            pass
        elif event["type"] == "tool_result":
            pass
        elif event["type"] == "final":
            final_text = event["payload"]["text"]
            print(final_text)
    print("".join(collected))

if __name__ == "__main__":
    asyncio.run(main("你可以有哪些动作"))
