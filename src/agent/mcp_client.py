# mcp_client.py — The bridge between the agent loop and the 3 MCP servers.
# Instead of using the MCP protocol's stdio transport (which requires
# subprocess management), we call the server handler functions directly.
# This is functionally identical for local dev — same tool definitions,
# same execution, just without the process overhead.

from src.mcp_servers.gmail_server import handle_list_tools as gmail_tools, handle_call_tool as gmail_call
from src.mcp_servers.calendar_server import handle_list_tools as cal_tools, handle_call_tool as cal_call
from src.mcp_servers.notion_server import handle_list_tools as notion_tools, handle_call_tool as notion_call

# Map: tool name → which server handles it
# Claude picks a tool by name — we use this map to route the call.
TOOL_ROUTING = {
    "list_emails":    ("gmail",    gmail_call),
    "get_email":      ("gmail",    gmail_call),
    "create_draft":   ("gmail",    gmail_call),
    "list_events":    ("calendar", cal_call),
    "check_conflicts":("calendar", cal_call),
    "get_free_slots": ("calendar", cal_call),
    "create_event":   ("calendar", cal_call),
    "search_pages":   ("notion",   notion_call),
    "get_page":       ("notion",   notion_call),
    "create_task":    ("notion",   notion_call),
    "update_task":    ("notion",   notion_call),
}

class MCPClient:

    async def list_all_tools(self) -> list:
        """
        Collect tool definitions from all 3 servers and convert to
        the format Claude's API expects: {"name", "description", "input_schema"}.
        These definitions are sent to Claude on every API call — they're how
        Claude knows what tools exist and when to use each one.
        """
        all_tools = []
        for tool_fn in [gmail_tools, cal_tools, notion_tools]:
            tools = await tool_fn()
            for t in tools:
                all_tools.append({
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.inputSchema  # Claude API uses input_schema, not inputSchema
                })
        return all_tools

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """Route a tool call to the correct server and return the result as string."""
        if tool_name not in TOOL_ROUTING:
            return f"Error: unknown tool '{tool_name}'"
        server_name, handler = TOOL_ROUTING[tool_name]
        result = await handler(tool_name, arguments)
        return result[0].text if result else "No result"

    def get_server_for_tool(self, tool_name: str) -> str:
        return TOOL_ROUTING.get(tool_name, ("unknown", None))[0]