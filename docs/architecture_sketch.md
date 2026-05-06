# Architecture — Before vs After MCP

## WITHOUT MCP
User -> FastAPI -> custom_gmail_handler.py, custom_calendar_handler.py, custom_notion_handler.py
# 3 auth flows, 3 schemas, ~450 lines of glue

## WITH MCP
User -> FastAPI -> Claude Agent -> MCP Client -> [gmail | calendar | notion]_mcp_server
# 1 protocol, 1 client, ~80 lines

## Key Design Decisions
1. Write safety: confirmation required before all state-changing tool calls
2. Fallback: agent continues if one server fails
3. Security: sanitize inputs before agent sees them
