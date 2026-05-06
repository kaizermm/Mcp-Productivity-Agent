import asyncio, base64, os
from email.mime.text import MIMEText
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import mcp.server.stdio
import mcp.types as types
from mcp.server import Server
from src.monitoring.tool_logger import timed_tool_call

load_dotenv()
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.compose']
server = Server("gmail-mcp")

def get_gmail_service():
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if creds.expired and creds.refresh_token: creds.refresh(Request())
    return build("gmail", "v1", credentials=creds)

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(name="list_emails",
            description="List recent emails from Gmail inbox. Use when user asks about emails, messages, or inbox. Returns IDs, subjects, senders, dates.",
            inputSchema={"type":"object","properties":{
                "max_results":{"type":"integer","default":10},
                "query":{"type":"string","description":"Gmail search query e.g. 'from:boss@co.com' or 'is:unread'"}}}),
        types.Tool(name="get_email",
            description="Get full content of a specific email by ID. Use after list_emails to read the actual message.",
            inputSchema={"type":"object","properties":{"message_id":{"type":"string"}},"required":["message_id"]}),
        types.Tool(name="create_draft",
            description="Create a Gmail draft. NEVER sends automatically — draft only. User must review and send manually.",
            inputSchema={"type":"object","properties":{
                "to":{"type":"string"},"subject":{"type":"string"},"body":{"type":"string"}},
                "required":["to","subject","body"]}),
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        gmail = get_gmail_service()
        if name == "list_emails":
            def _call():
                r = gmail.users().messages().list(userId="me",maxResults=arguments.get("max_results",10),q=arguments.get("query","")).execute()
                results = []
                for m in r.get("messages",[])[:arguments.get("max_results",10)]:
                    d = gmail.users().messages().get(userId="me",id=m["id"],format="metadata",metadataHeaders=["Subject","From","Date"]).execute()
                    h = {x["name"]:x["value"] for x in d["payload"]["headers"]}
                    results.append({"id":m["id"],"subject":h.get("Subject"),"from":h.get("From"),"date":h.get("Date")})
                return results
            result = timed_tool_call("gmail", name, arguments, _call)
        elif name == "get_email":
            def _call():
                msg = gmail.users().messages().get(userId="me",id=arguments["message_id"],format="full").execute()
                body = ""
                for part in msg.get("payload",{}).get("parts",[]):
                    if part.get("mimeType")=="text/plain":
                        body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8"); break
                h = {x["name"]:x["value"] for x in msg["payload"]["headers"]}
                return {"subject":h.get("Subject"),"from":h.get("From"),"body":body[:2000]}
            result = timed_tool_call("gmail", name, arguments, _call)
        elif name == "create_draft":
            def _call():
                msg = MIMEText(arguments["body"])
                msg["to"]=arguments["to"]; msg["subject"]=arguments["subject"]
                raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
                d = gmail.users().drafts().create(userId="me",body={"message":{"raw":raw}}).execute()
                return {"draft_id":d["id"],"status":"draft created — NOT sent"}
            result = timed_tool_call("gmail", name, arguments, _call)
        else: return [types.TextContent(type="text",text=f"Unknown tool: {name}")]
        return [types.TextContent(type="text",text=str(result))]
    except Exception as e:
        return [types.TextContent(type="text",text=f"Error in {name}: {str(e)}")]

async def main():
    async with mcp.server.stdio.stdio_server() as (r, w):
        await server.run(r, w, server.create_initialization_options())

if __name__ == "__main__": asyncio.run(main())