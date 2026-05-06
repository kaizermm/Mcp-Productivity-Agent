import json, time
from datetime import datetime, timezone
from pathlib import Path

LOG_FILE = Path("logs/tool_calls.jsonl")

def log_tool_call(server_name: str, tool: str, args: dict,
                   result: str = None, error: str = None, latency_ms: float = None):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "server": server_name,
        "tool": tool,
        "args": args,
        "result_preview": str(result)[:300] if result else None,
        "error": error,
        "latency_ms": round(latency_ms, 2) if latency_ms else None,
        "success": error is None
    }
    LOG_FILE.parent.mkdir(exist_ok=True, parents=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

def timed_tool_call(server_name: str, tool: str, args: dict, fn):
    """Times any function call and logs automatically."""
    start = time.time()
    try:
        result = fn()
        latency = (time.time() - start) * 1000
        log_tool_call(server_name, tool, args, result=str(result), latency_ms=latency)
        return result
    except Exception as e:
        latency = (time.time() - start) * 1000
        log_tool_call(server_name, tool, args, error=str(e), latency_ms=latency)
        raise

def get_tool_stats() -> dict:
    """Per-server stats for monitoring dashboard."""
    if not LOG_FILE.exists(): return {}
    calls = [json.loads(l) for l in LOG_FILE.read_text(encoding="utf-8").strip().splitlines() if l]
    servers = {}
    for c in calls:
        s = c["server"]
        if s not in servers: servers[s] = {"calls":0,"errors":0,"latencies":[]}
        servers[s]["calls"] += 1
        if not c["success"]: servers[s]["errors"] += 1
        if c["latency_ms"]: servers[s]["latencies"].append(c["latency_ms"])
    return {s:{"calls":v["calls"],"errors":v["errors"],
               "avg_latency_ms":round(sum(v["latencies"])/len(v["latencies"]),1) if v["latencies"] else 0}
            for s,v in servers.items()}

if __name__ == "__main__":
    log_tool_call("test", "ping", {}, result="pong", latency_ms=12.5)
    print("✓ Logger working:", get_tool_stats())