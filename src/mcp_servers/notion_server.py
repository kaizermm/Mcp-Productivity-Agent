import asyncio, os
from dotenv import load_dotenv
from notion_client import Client
import mcp.server.stdio, mcp.types as types
from mcp.server import Server
from src.monitoring.tool_logger import timed_tool_call

load_dotenv()
server = Server("notion-mcp")

def get_notion() -> Client: return Client(auth=os.environ["NOTION_TOKEN"])

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(name="search_pages",
            description="Search Notion pages and databases by keyword. Use when user asks about notes, docs, or tasks in Notion.",
            inputSchema={"type":"object","properties":{"query":{"type":"string"},"max_results":{"type":"integer","default":5}},"required":["query"]}),
        types.Tool(name="get_page",
            description="Get full content of a Notion page by ID. Use after search_pages to read the actual page.",
            inputSchema={"type":"object","properties":{"page_id":{"type":"string"}},"required":["page_id"]}),
        types.Tool(name="create_task",
            description="Create a new task in the Notion tasks database. REQUIRES explicit user confirmation. Write action.",
            inputSchema={"type":"object","properties":{"title":{"type":"string"},"due_date":{"type":"string","description":"YYYY-MM-DD optional"},"notes":{"type":"string"}},"required":["title"]}),
        types.Tool(name="update_task",
            description="Update an existing Notion task. REQUIRES explicit user confirmation. Write action.",
            inputSchema={"type":"object","properties":{"page_id":{"type":"string"},"status":{"type":"string","enum":["Not started","In progress","Done"]},"title":{"type":"string"}},"required":["page_id"]}),
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        n = get_notion()

        if name == "search_pages":
            def _call():
                r = n.search(query=arguments["query"], page_size=arguments.get("max_results", 5))
                results = []
                for p in r.get("results", []):
                    # safely extract title — property key varies by database setup
                    title = "Untitled"
                    props = p.get("properties", {})
                    for key in ("title", "Name", "Task", "name"):
                        if key in props:
                            arr = props[key].get("title", [])
                            if arr:
                                title = arr[0].get("plain_text", "Untitled")
                                break
                    results.append({
                        "id": p["id"],
                        "title": title,
                        "type": p["object"]
                    })
                return results
            result = timed_tool_call("notion", name, arguments, _call)

        elif name == "get_page":
            def _call():
                page = n.pages.retrieve(page_id=arguments["page_id"])
                blocks = n.blocks.children.list(block_id=arguments["page_id"])
                txt = [
                    b.get("paragraph", {}).get("rich_text", [{}])[0].get("plain_text", "")
                    for b in blocks.get("results", [])
                    if b.get("type") == "paragraph" and b["paragraph"].get("rich_text")
                ]
                return {"id": page["id"], "content": " ".join(txt)[:3000]}
            result = timed_tool_call("notion", name, arguments, _call)

        elif name == "create_task":
            def _call():
                # Search without API filter — Notion changed "database" to "data_source"
                # in some workspace types. Filter in Python to handle both.
                search_result = n.search(query="Tasks")
                db_results = [
                    r for r in search_result.get("results", [])
                    if r.get("object") in ("database", "data_source")
                ]
                if not db_results:
                    raise ValueError(
                        "No 'Tasks' database found. "
                        "Create a database named 'Tasks' in Notion and connect "
                        "your integration to it via the ... menu → Connections."
                    )
                db_id = db_results[0]["id"]
                props = {
                    "title": {"title": [{"text": {"content": arguments["title"]}}]}
                }
                if arguments.get("due_date"):
                    props["Due"] = {"date": {"start": arguments["due_date"]}}
                page = n.pages.create(
                    parent={"database_id": db_id},
                    properties=props
                )
                return {
                    "page_id": page["id"],
                    "title": arguments["title"],
                    "status": "created"
                }
            result = timed_tool_call("notion", name, arguments, _call)

        elif name == "update_task":
            def _call():
                def _call():
                    db_id = "350460189ace801097c2000bcf0495e7"
                    props = {
                        "title": {"title": [{"text": {"content": arguments["title"]}}]}
                    }
                    if arguments.get("due_date"):
                        props["Due"] = {"date": {"start": arguments["due_date"]}}
                    page = n.pages.create(
                        parent={"database_id": db_id},
                        properties=props
                    )
                    return {"page_id": page["id"], "title": arguments["title"], "status": "created"}

        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

        return [types.TextContent(type="text", text=str(result))]

    except Exception as e:
        return [types.TextContent(type="text", text=f"Error in {name}: {str(e)}")]


async def main():
    async with mcp.server.stdio.stdio_server() as (r, w):
        await server.run(r, w, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
