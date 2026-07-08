from app.config import settings

try:
    from langfuse import Langfuse
    _LANGFUSE_AVAILABLE = True
except ImportError:
    _LANGFUSE_AVAILABLE = False


class Tracer:
    """Wraps Langfuse tracing (SDK v4). Silently no-ops if keys are absent
    or the package isn't installed, so the app runs identically with or
    without it.

    Credentials are passed explicitly rather than relying on get_client()'s
    environment-variable auto-detection: pydantic-settings reads .env into
    the Settings object directly without populating os.environ, so the SDK's
    own env-var lookup never sees the keys even when settings has them."""

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
                base_url=settings.langfuse_host,
            )

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