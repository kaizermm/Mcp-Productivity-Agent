import asyncio
from dotenv import load_dotenv
load_dotenv()

# DO NOT set TEST_MODE here — we want the real confirmation prompt

from src.agent.agent_loop import run_agent

async def main():
    print("Testing confirmation gate...")
    print("When prompted, type 'no' to test that the agent respects your answer.\n")

    # This asks Claude to create a Notion task — a write action.
    # The agent should: (1) read Notion first, (2) show confirmation prompt, (3) wait for input.
    # Type 'no' at the prompt — agent should confirm it cancelled.
    result = await run_agent("Create a Notion task called 'Test confirmation gate'")

    print(f"\n🤖 Response: {result['response']}")
    print(f"Tool trace: {result['tool_trace']}")

asyncio.run(main())