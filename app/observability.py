from app.config import settings

try:
    from langfuse import get_client
    _LANGFUSE_AVAILABLE = True
except ImportError:
    _LANGFUSE_AVAILABLE = False


class Tracer:
    """Wraps Langfuse tracing (SDK v4). Silently no-ops if keys are absent
    or the package isn't installed, so the app runs identically with or
    without it. get_client() reads LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY
    / LANGFUSE_HOST from the environment automatically."""

    def __init__(self):
        self.enabled = bool(
            _LANGFUSE_AVAILABLE
            and settings.langfuse_public_key
            and settings.langfuse_secret_key
        )
        self._client = get_client() if self.enabled else None

    def start_trace(self, trace_id: str, question: str, researcher: str | None):
        if not self.enabled:
            return None
        return self._client.start_observation(
            name="research_query",
            as_type="span",
            input={"question": question},
            metadata={"trace_id": trace_id, "researcher": researcher},
        )

    def log_tool_call(self, trace, tool_name: str, args: dict, result: dict, duration_ms: float):
        if not self.enabled or trace is None:
            return
        child = trace.start_observation(
            name=tool_name,
            as_type="tool",
            input=args,
        )
        child.update(output=result, metadata={"duration_ms": duration_ms})
        child.end()

    def end_trace(self, trace, answer: str):
        if not self.enabled or trace is None:
            return
        trace.update(output={"answer": answer})
        trace.end()
        self._client.flush()


tracer = Tracer()