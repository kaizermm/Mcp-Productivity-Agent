import os

# Tools that modify data — ALWAYS require user confirmation before executing.
# Read-only tools (list_emails, list_events, search_pages, etc.) skip confirmation.
# Write tools (anything that creates or changes data) go through the gate.
WRITE_TOOLS = {
    "create_draft",   # Gmail: creates a draft email
    "create_event",   # Calendar: creates a calendar event
    "create_task",    # Notion: creates a task in database
    "update_task",    # Notion: modifies an existing task
}

def requires_confirmation(tool_name: str) -> bool:
    """Return True if this tool modifies data and needs user approval."""
    return tool_name in WRITE_TOOLS


async def get_user_confirmation(tool_name: str, args: dict) -> bool:
    """
    Ask the user to approve a write action.

    In TEST_MODE (set TEST_MODE=1 in env): auto-approves so tests don't hang.
    In terminal mode: prompts the user directly.
    In production (Day 5): this will be replaced by a WebSocket event to the UI.
    
    Why a separate module? Because confirmation behavior differs per environment.
    Development = terminal prompt. Testing = auto-approve. Production = UI event.
    Keeping it here means you swap one function, not hunt through the codebase.
    """
    if os.getenv("TEST_MODE"):
        print(f"  [TEST_MODE] Auto-approving: {tool_name}")
        return True

    # Format a human-readable summary of what's about to happen
    action_summary = _format_action(tool_name, args)
    print(f"\n⚠️  Confirmation required")
    print(f"   Action : {tool_name}")
    print(f"   Details: {action_summary}")
    answer = input("   Proceed? (yes/no): ").strip().lower()
    return answer in {"yes", "y"}


def _format_action(tool_name: str, args: dict) -> str:
    """Make the confirmation prompt human-readable."""
    if tool_name == "create_draft":
        return f"Draft email to {args.get('to')} — Subject: {args.get('subject')}"
    elif tool_name == "create_event":
        return f"Calendar event '{args.get('title')}' at {args.get('start_time')}"
    elif tool_name == "create_task":
        return f"Notion task: '{args.get('title')}'"
    elif tool_name == "update_task":
        return f"Update task {args.get('page_id')} → status: {args.get('status')}"
    return str(args)