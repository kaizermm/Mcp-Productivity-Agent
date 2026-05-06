import httpx, asyncio, json, time
from datetime import datetime
from pathlib import Path

API_URL = "http://localhost:8000/eval"

# 15 tasks across 3 difficulty levels.
# expected_tools: which tools SHOULD be called — used to measure routing accuracy.
# type: simple (1 tool), medium (2-3 tools, 1 service), complex (multi-service)
EVAL_TASKS = [
    # ── SIMPLE — single tool, one service ─────────────────────────
    {"id": 1,  "query": "What are my 3 most recent emails?",                          "expected_tools": ["list_emails"],                          "type": "simple"},
    {"id": 2,  "query": "What's on my calendar this week?",                          "expected_tools": ["list_events"],                          "type": "simple"},
    {"id": 3,  "query": "Search my Notion for anything about work",                  "expected_tools": ["search_pages"],                         "type": "simple"},
    {"id": 4,  "query": "Do I have any free time tomorrow?",                         "expected_tools": ["get_free_slots"],                       "type": "simple"},
    {"id": 5,  "query": "Check my emails for anything from LinkedIn",               "expected_tools": ["list_emails"],                          "type": "simple"},
    # ── MEDIUM — multi-tool, single service ───────────────────────
    {"id": 6,  "query": "Check my emails and tell me which ones need a reply",       "expected_tools": ["list_emails", "get_email"],            "type": "medium"},
    {"id": 7,  "query": "What meetings do I have and when is my next free slot?",  "expected_tools": ["list_events", "get_free_slots"],       "type": "medium"},
    {"id": 8,  "query": "Summarize what I have going on this week from email and calendar", "expected_tools": ["list_emails", "list_events"],    "type": "medium"},
    {"id": 9,  "query": "Are there any conflicts if I schedule a meeting at 2pm today?", "expected_tools": ["check_conflicts"],                 "type": "medium"},
    {"id": 10, "query": "Find emails from this week and check if any mention a meeting", "expected_tools": ["list_emails", "get_email"],           "type": "medium"},
    # ── COMPLEX — cross-service, multi-step ───────────────────────
    {"id": 11, "query": "Check my emails and calendar and give me a productivity summary for today", "expected_tools": ["list_emails", "list_events"], "type": "complex"},
    {"id": 12, "query": "What should I focus on today based on my emails and Notion?",  "expected_tools": ["list_emails", "search_pages"],        "type": "complex"},
    {"id": 13, "query": "Check my calendar and find a free slot for a 1-hour meeting this week", "expected_tools": ["list_events", "get_free_slots"], "type": "complex"},
    {"id": 14, "query": "Give me a full briefing: recent emails, upcoming events, and Notion tasks", "expected_tools": ["list_emails", "list_events", "search_pages"], "type": "complex"},
    {"id": 15, "query": "Are there any emails about meetings I need to add to my calendar?", "expected_tools": ["list_emails", "check_conflicts"],   "type": "complex"},
]


async def run_eval_task(client: httpx.AsyncClient, task: dict) -> dict:
    start = time.time()
    try:
        r = await client.post(API_URL, json={"query": task["query"]}, timeout=60.0)
        data = r.json()
        latency = (time.time() - start) * 1000

        tools_called = [t["tool"] for t in data.get("tool_trace", [])]
        expected = task["expected_tools"]
        routing_correct = any(e in tools_called for e in expected)
        completed = data.get("status") == "complete" and len(data.get("response", "")) > 50

        return {
            "id": task["id"], "type": task["type"],
            "completed": completed, "routing_correct": routing_correct,
            "tools_called": tools_called, "latency_ms": round(latency, 1),
            "response_len": len(data.get("response", "")), "status": data.get("status")
        }
    except Exception as e:
        return {"id": task["id"], "type": task["type"], "completed": False,
                "routing_correct": False, "error": str(e), "latency_ms": 0}


async def main():
    print("MCP Agent Evaluation Suite — 15 Tasks")
    print("Make sure uvicorn is running: uvicorn src.api.main:app --reload --port 8000\n")

    results = []
    async with httpx.AsyncClient() as client:
        for task in EVAL_TASKS:
            print(f"Running task {task['id']:02d}/{len(EVAL_TASKS)} [{task['type']:7s}] {task['query'][:55]}...")
            result = await run_eval_task(client, task)
            results.append(result)
            status = "✓" if result["completed"] else "✗"
            routing = "✓" if result["routing_correct"] else "✗"
            print(f"  complete:{status} routing:{routing} tools:{result.get('tools_called',[])} {result['latency_ms']:.0f}ms")
            await asyncio.sleep(1)  # avoid rate limit

    # ── Calculate metrics ────────────────────────────────────────────
    total = len(results)
    completed = sum(1 for r in results if r["completed"])
    routed = sum(1 for r in results if r["routing_correct"])
    avg_latency = sum(r["latency_ms"] for r in results) / total

    by_type = {}
    for r in results:
        t = r["type"]
        if t not in by_type: by_type[t] = {"total": 0, "completed": 0}
        by_type[t]["total"] += 1
        if r["completed"]: by_type[t]["completed"] += 1

    print(f"\n{'='*60}")
    print(f"EVAL RESULTS")
    print(f"{'='*60}")
    print(f"Task completion:   {completed}/{total} ({completed/total*100:.0f}%)")
    print(f"Tool routing:      {routed}/{total} ({routed/total*100:.0f}%)")
    print(f"Avg latency:       {avg_latency:.0f}ms")
    print(f"\nBy difficulty:")
    for t, v in by_type.items():
        print(f"  {t:8s}: {v['completed']}/{v['total']} ({v['completed']/v['total']*100:.0f}%)")

    # Save results to file for README
    Path("docs/eval_results.json").write_text(json.dumps({
        "run_date": datetime.now().isoformat(),
        "completion_rate": f"{completed/total*100:.0f}%",
        "routing_accuracy": f"{routed/total*100:.0f}%",
        "avg_latency_ms": round(avg_latency),
        "by_type": {t: f"{v['completed']}/{v['total']}" for t, v in by_type.items()},
        "results": results
    }, indent=2))
    print(f"\n✅ Results saved to docs/eval_results.json")
    print(f"   Use these numbers in your README.")

asyncio.run(main())