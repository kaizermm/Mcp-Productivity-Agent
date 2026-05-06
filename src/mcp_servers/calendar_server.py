import asyncio
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import mcp.server.stdio, mcp.types as types
from mcp.server import Server
from src.monitoring.tool_logger import timed_tool_call

load_dotenv()
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly','https://www.googleapis.com/auth/calendar.events']
server = Server("calendar-mcp")

def get_cal():
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if creds.expired and creds.refresh_token: creds.refresh(Request())
    return build("calendar", "v3", credentials=creds)

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(name="list_events",
            description="List upcoming Google Calendar events. Use when user asks about schedule, meetings, what's on today or this week.",
            inputSchema={"type":"object","properties":{"days_ahead":{"type":"integer","default":7},"max_results":{"type":"integer","default":10}}}),
        types.Tool(name="check_conflicts",
            description="Check if a specific time slot has a calendar conflict. Always call this before create_event.",
            inputSchema={"type":"object","properties":{"start_time":{"type":"string","description":"ISO 8601 e.g. 2025-04-20T14:00:00"},"end_time":{"type":"string"}},"required":["start_time","end_time"]}),
        types.Tool(name="get_free_slots",
            description="Find available time slots for scheduling a meeting. Use when user wants to know when they are free.",
            inputSchema={"type":"object","properties":{"days_ahead":{"type":"integer","default":5},"duration_minutes":{"type":"integer","default":30}}}),
        types.Tool(name="create_event",
            description="Create a Google Calendar event. REQUIRES explicit user confirmation. Always check_conflicts first. Write action.",
            inputSchema={"type":"object","properties":{"title":{"type":"string"},"start_time":{"type":"string"},"end_time":{"type":"string"},"description":{"type":"string","default":""},"attendees":{"type":"array","items":{"type":"string"},"default":[]}},"required":["title","start_time","end_time"]}),
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        cal = get_cal(); now = datetime.now(timezone.utc)
        if name == "list_events":
            def _call():
                end = now + timedelta(days=arguments.get("days_ahead",7))
                ev = cal.events().list(calendarId="primary",timeMin=now.isoformat(),timeMax=end.isoformat(),maxResults=arguments.get("max_results",10),singleEvents=True,orderBy="startTime").execute()
                return [{"title":e.get("summary"),"start":e["start"].get("dateTime",e["start"].get("date")),"id":e["id"]} for e in ev.get("items",[])]
            result = timed_tool_call("calendar", name, arguments, _call)
        elif name == "check_conflicts":
            def _call():
                fb = cal.freebusy().query(body={"timeMin":arguments["start_time"]+"Z","timeMax":arguments["end_time"]+"Z","items":[{"id":"primary"}]}).execute()
                busy = fb["calendars"]["primary"]["busy"]
                return {"has_conflict":len(busy)>0,"conflicts":busy}
            result = timed_tool_call("calendar", name, arguments, _call)
        elif name == "get_free_slots":
            def _call():
                slots=[]; dur=timedelta(minutes=arguments.get("duration_minutes",30))
                for day in range(arguments.get("days_ahead",5)):
                    d=(now+timedelta(days=day+1)).replace(hour=9,minute=0,second=0,microsecond=0)
                    while d.hour<17:
                        fb=cal.freebusy().query(body={"timeMin":d.isoformat(),"timeMax":(d+dur).isoformat(),"items":[{"id":"primary"}]}).execute()
                        if not fb["calendars"]["primary"]["busy"]: slots.append({"start":d.isoformat(),"end":(d+dur).isoformat()})
                        d+=dur
                        if len(slots)>=5: break
                    if len(slots)>=5: break
                return slots
            result = timed_tool_call("calendar", name, arguments, _call)
        elif name == "create_event":
            def _call():
                ev = cal.events().insert(calendarId="primary",body={"summary":arguments["title"],"description":arguments.get("description",""),"start":{"dateTime":arguments["start_time"],"timeZone":"UTC"},"end":{"dateTime":arguments["end_time"],"timeZone":"UTC"},"attendees":[{"email":e} for e in arguments.get("attendees",[])],}).execute()
                return {"event_id":ev["id"],"link":ev.get("htmlLink"),"status":"created"}
            result = timed_tool_call("calendar", name, arguments, _call)
        else: return [types.TextContent(type="text",text=f"Unknown: {name}")]
        return [types.TextContent(type="text",text=str(result))]
    except Exception as e:
        return [types.TextContent(type="text",text=f"Error in {name}: {str(e)}")]

async def main():
    async with mcp.server.stdio.stdio_server() as (r,w):
        await server.run(r, w, server.create_initialization_options())

if __name__ == "__main__": asyncio.run(main())