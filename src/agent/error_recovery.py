
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# ── RETRY DECORATOR ────────────────────────────────────────────────────────
# Wraps any async function: if it throws, wait and retry up to 3 times.
# wait_exponential: first retry after 2s, second after 4s, max 10s.
# Why exponential? Avoids hammering a rate-limited API repeatedly.
def with_retry(async_fn):
    """Decorator — adds retry logic to any async tool call."""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
        reraise=True
    )(async_fn)


# ── SERVICE HEALTH TRACKER ─────────────────────────────────────────────────
# Tracks consecutive failures per service.
# After 3 failures: service is "degraded" → return fallback instead of retrying.
class ServiceHealthTracker:
    
    def __init__(self):
        self.failures  = {"gmail": 0, "calendar": 0, "notion": 0}
        self.successes = {"gmail": 0, "calendar": 0, "notion": 0}

    def record_failure(self, service: str):
        """Call this whenever a tool throws an exception."""
        if service in self.failures:
            self.failures[service] += 1

    def record_success(self, service: str):
        """Call this on successful tool call — resets failure count."""
        if service in self.failures:
            self.failures[service] = 0
            self.successes[service] += 1

    def is_degraded(self, service: str) -> bool:
        """True if this service has failed 3+ times in a row."""
        return self.failures.get(service, 0) >= 3

    def get_fallback_message(self, service: str) -> str:
        """
        Human-readable fallback when a service is degraded.
        Claude receives this as the tool_result and uses it in its response
        to explain the situation to the user.
        """
        messages = {
            "gmail":    "Gmail is currently unavailable. I can still work with your Calendar and Notion.",
            "calendar": "Google Calendar is unavailable. I've noted the event details — add it manually when it's back.",
            "notion":   "Notion is unavailable. I'll save the task details here for you to add manually later.",
        }
        return messages.get(service, f"{service} is currently unavailable.")

    def get_status_report(self) -> dict:
        """For the monitoring dashboard on Day 5."""
        return {
            s: {"failures": self.failures[s], "successes": self.successes[s], "degraded": self.is_degraded(s)}
            for s in ["gmail", "calendar", "notion"]
        }