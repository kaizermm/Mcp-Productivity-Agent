import anthropic
import os
from pathlib import Path
from dotenv import load_dotenv
from src.agent.mcp_client import MCPClient
from src.agent.confirmation import requires_confirmation, get_user_confirmation
from src.agent.error_recovery import ServiceHealthTracker
from src.monitoring.tool_logger import log_tool_call
from src.security.sanitizer import sanitize_input, log_security_event
from src.security.audit_log import log_write_action


load_dotenv()

client = anthropic.Anthropic()
MAX_ITERATIONS = 10   # safety guard against infinite loops
health = ServiceHealthTracker()


async def run_agent(user_query: str, system_prompt: str = None) -> dict:
    """
    The main agent loop.
    Returns: {"status": "complete"|"max_iterations"|"error", "response": str, "tool_trace": list}
    """
    clean_query, issues = sanitize_input(user_query)
    if issues:
        log_security_event(user_query, issues)
        print(f"⚠ Security: {issues} detected and redacted from input")
    user_query = clean_query

    if system_prompt is None:
        system_prompt = Path("prompts/system_prompt_v1.txt").read_text()

    mcp = MCPClient()
    available_tools = await mcp.list_all_tools()

    messages = [{"role": "user", "content": user_query}]
    tool_trace = []

    for iteration in range(MAX_ITERATIONS):

        # ── Call Claude API ──────────────────────────────────────────
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=system_prompt,
            tools=available_tools,
            messages=messages
        )

        # ── Check if Claude is done ──────────────────────────────────
        if response.stop_reason == "end_turn":
            final = ""
            for block in response.content:
                if hasattr(block, "text"): final += block.text
            return {"status": "complete", "response": final, "tool_trace": tool_trace}

        # ── Claude wants to call tools ───────────────────────────────
        tool_results = []
        for block in response.content:
            if block.type != "tool_use": continue

            tool_name = block.name
            tool_args = block.input
            server = mcp.get_server_for_tool(tool_name)

            # ── Confirmation gate: ask before any write action ───────
            if requires_confirmation(tool_name):
                confirmed = await get_user_confirmation(tool_name, tool_args)
                if not confirmed:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "User declined this action. Do not retry."
                    })
                    tool_trace.append({"tool": tool_name, "status": "declined_by_user"})
                    continue

            # ── Execute the tool ─────────────────────────────────────
            try:
                import time
                start = time.time()
                result = await mcp.call_tool(tool_name, tool_args)
                latency = (time.time() - start) * 1000

                log_tool_call(server, tool_name, tool_args, result=result, latency_ms=latency)
                tool_trace.append({"tool": tool_name, "args": tool_args, "result_preview": str(result)[:150], "latency_ms": round(latency, 1)})
                health.record_success(server)

                # ── Audit log: only for write actions, AFTER success ─
                if requires_confirmation(tool_name):
                    log_write_action(
                        tool=tool_name,
                        args=tool_args,
                        user_query=user_query,
                        confirmed=True,
                        result=result
                    )

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(result)
                })

            except Exception as e:
                health.record_failure(server)
                log_tool_call(server, tool_name, tool_args, error=str(e))
                fallback = health.get_fallback_message(server) if health.is_degraded(server) else f"Tool error: {str(e)}"
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": fallback,
                    "is_error": True
                })

        # ── Feed all tool results back to Claude ─────────────────────
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    return {"status": "max_iterations_reached", "tool_trace": tool_trace}