import asyncio
from dotenv import load_dotenv
load_dotenv()

async def test_gmail():
    print("\n── Gmail ──────────────────────────")
    from src.mcp_servers.gmail_server import handle_call_tool
    r = await handle_call_tool("list_emails", {"max_results": 2})
    print("  list_emails:", r[0].text[:120])
    print("  ✓ Gmail working")

async def test_calendar():
    print("\n── Calendar ───────────────────────")
    from src.mcp_servers.calendar_server import handle_call_tool
    r = await handle_call_tool("list_events", {"days_ahead": 7})
    print("  list_events:", r[0].text[:120])
    print("  ✓ Calendar working")

async def test_notion():
    print("\n── Notion ─────────────────────────")
    from src.mcp_servers.notion_server import handle_call_tool
    r = await handle_call_tool("search_pages", {"query": "", "max_results": 2})
    print("  search_pages:", r[0].text[:120])
    print("  ✓ Notion working")

async def main():
    await test_gmail()
    await test_calendar()
    await test_notion()
    print("\n✅ All 3 servers working — ready for Day 3")

asyncio.run(main())