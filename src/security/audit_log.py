import json
from datetime import datetime, timezone
from pathlib import Path

AUDIT_FILE = Path("logs/audit.jsonl")


def log_write_action(
    tool: str,
    args: dict,
    user_query: str,
    confirmed: bool,
    result: str,
    user_id: str = "default"
):
    """
    Log every write action taken by the agent.

    Fields explained:
    - tool         : which tool was called (create_event, create_task, etc.)
    - args         : exact arguments passed to the tool
    - user_query   : the ORIGINAL user request that triggered this action
                     Why? So you can compare what was asked vs what was done.
    - confirmed    : did the user explicitly approve this? (True/False)
    - result       : what the tool returned (truncated to 300 chars)
    - user_id      : for multi-user systems — tracks which user triggered it
    """
    entry = {
        "timestamp":    datetime.now(timezone.utc).isoformat(),
        "user_id":       user_id,
        "user_query":    user_query[:300],
        "tool":          tool,
        "args":          args,
        "user_confirmed": confirmed,
        "result_summary": str(result)[:300],
        "action_type":  "WRITE"
    }
    AUDIT_FILE.parent.mkdir(exist_ok=True, parents=True)
    with open(AUDIT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def get_audit_trail(limit: int = 20) -> list:
    """Return the N most recent audit entries for the monitoring dashboard."""
    if not AUDIT_FILE.exists():
        return []
    lines = AUDIT_FILE.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(l) for l in lines[-limit:]]


def get_write_stats() -> dict:
    """Summary stats: total writes, confirmed vs auto, per-tool breakdown."""
    entries = get_audit_trail(limit=1000)
    if not entries: return {}
    tool_counts = {}
    confirmed_count = 0
    for e in entries:
        t = e["tool"]
        tool_counts[t] = tool_counts.get(t, 0) + 1
        if e.get("user_confirmed"): confirmed_count += 1
    return {
        "total_writes": len(entries),
        "user_confirmed": confirmed_count,
        "auto_confirmed": len(entries) - confirmed_count,
        "by_tool": tool_counts
    }