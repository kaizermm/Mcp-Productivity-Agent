from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import os, time
from dotenv import load_dotenv

load_dotenv()
os.environ["TEST_MODE"] = "1"   # auto-confirm writes in API context

from src.agent.agent_loop import run_agent
from src.monitoring.tool_logger import get_tool_stats
from src.security.audit_log import get_audit_trail, get_write_stats

# ── Rate limiter: max 10 agent calls per minute per IP ────────────
# Why 10/minute? Enough for real use, too low for abuse or runaway loops.
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="MCP Productivity Agent", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class AgentRequest(BaseModel):
    query: str
    user_id: str = "default"

class AgentResponse(BaseModel):
    status: str
    response: str
    tool_trace: list
    latency_ms: float


# ── Health check — deployment platforms (Railway, Render) ping this ─
@app.get("/")
async def health():
    return {"status": "ok", "agent": "mcp-productivity-agent", "version": "1.0.0"}


# ── Main agent endpoint — n8n and clients call this ──────────────
@app.post("/agent", response_model=AgentResponse)
@limiter.limit("10/minute")
async def run_agent_endpoint(request: Request, body: AgentRequest):
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    if len(body.query) > 2000:
        raise HTTPException(status_code=400, detail="Query too long (max 2000 chars)")

    start = time.time()
    result = await run_agent(body.query)
    latency = (time.time() - start) * 1000

    return AgentResponse(
        status=result["status"],
        response=result.get("response", ""),
        tool_trace=result.get("tool_trace", []),
        latency_ms=round(latency, 1)
    )


# ── Monitoring endpoint — shows tool call stats ───────────────────
@app.get("/monitoring/stats")
async def monitoring_stats():
    """
    Returns per-service stats from logs/tool_calls.jsonl.
    Shows: call counts, error rates, avg latency per server.
    Use this to spot which service is slow or failing.
    """
    return {
        "tool_stats": get_tool_stats(),
        "write_stats": get_write_stats(),
        "audit_trail": get_audit_trail(limit=10)
    }


# ── Eval endpoint — run a single task and return full trace ───────
@app.post("/eval")
@limiter.limit("20/minute")
async def eval_task(request: Request, body: AgentRequest):
    """Used by the eval suite to run tasks and capture results."""
    start = time.time()
    result = await run_agent(body.query)
    latency = (time.time() - start) * 1000
    return {
        "query": body.query,
        "status": result["status"],
        "response": result.get("response", ""),
        "tool_trace": result.get("tool_trace", []),
        "tool_count": len(result.get("tool_trace", [])),
        "latency_ms": round(latency, 1)
    }