from app.config import settings

try:
    from langfuse import Langfuse
    _LANGFUSE_AVAILABLE = True
except ImportError:
    _LANGFUSE_AVAILABLE = False


class Tracer:
    """Wraps Langfuse tracing. Silently no-ops if keys are absent or the
    package isn't installed, so the app runs identically with or without it."""

    def __init__(self):
        self.enabled = bool(
            _LANGFUSE_AVAILABLE
            and settings.langfuse_public_key
            and settings.langfuse_secret_key
        )
        self._client = None
        if self.enabled:
            self._client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )

    def start_trace(self, trace_id: str, question: str, researcher: str | None):
        if not self.enabled:
            return None
        return self._client.trace(
            id=trace_id,
            name="research_query",
            input={"question": question},
            metadata={"researcher": researcher},
        )

    def log_tool_call(self, trace, tool_name: str, args: dict, result: dict, duration_ms: float):
        if not self.enabled or trace is None:
            return
        trace.span(
            name=tool_name,
            input=args,
            output=result,
            metadata={"duration_ms": duration_ms},
        )

    def end_trace(self, trace, answer: str):
        if not self.enabled or trace is None:
            return
        trace.update(output={"answer": answer})
        self._client.flush()


tracer = Tracer()