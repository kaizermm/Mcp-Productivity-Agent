import asyncio, os
from dotenv import load_dotenv
load_dotenv()

# Set TEST_MODE so write-action confirmations auto-approve
# Remove this line when testing confirmation behavior manually
os.environ["TEST_MODE"] = "1"
os.environ["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from src.agent.agent_loop import run_agent

# ── 5 TEST TASKS ──────────────────────────────────────────────────
# These tasks cover the 3 services and multi-step workflows.
# Run them one at a time — read Claude's response and tool trace.
TEST_TASKS = [
    "What are my 3 most recent emails?",                                # Gmail read
    "What's on my calendar for the next 7 days?",                       # Calendar read
    "Search my Notion for anything related to 'project'",               # Notion read
    "Check my emails and tell me if there's anything urgent",           # Gmail read + reasoning
    "What am I doing today, and do I have any free time this week?",    # Calendar multi-tool
]

async def run_task(task: str, task_num: int):
    print(f"\n{'='*60}")
    print(f"Task {task_num}: {task}")
    print(f"{'='*60}")

    result = await run_agent(task)

    print(f"\n🤖 Agent Response:")
    print(result["response"])

    print(f"\n📋 Tool Trace ({len(result['tool_trace'])} calls):")
    for i, call in enumerate(result["tool_trace"], 1):
        print(f"  {i}. {call.get('tool')} — {call.get('latency_ms', '?')}ms")
        if call.get("result_preview"):
            print(f"     → {call['result_preview'][:80]}")

    print(f"\nStatus: {result['status']}")

async def main():
    print("MCP Productivity Agent — Day 3 Test")
    print("Running 5 tasks against live APIs...\n")
    for i, task in enumerate(TEST_TASKS, 1):
        await run_task(task, i)
    print(f"\n\n✅ All 5 tasks complete")

asyncio.run(main())