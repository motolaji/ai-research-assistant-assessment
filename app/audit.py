from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import threading

@dataclass
class AuditEntry:
    trace_id: str
    question: str
    researcher: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tool_calls: list[dict] = field(default_factory=list)
    total_duration_ms: float = 0.0
    answer_preview: str = ""
    errors: list[str] = field(default_factory=list)

    def record_tool_call(self, tool: str, args: dict, duration_ms: float, policies_fired: list[str]):
        self.tool_calls.append({
            "tool": tool,
            "args": args,
            "duration_ms": round(duration_ms, 2),
            "policies_fired": policies_fired,
        })

    def finalise(self, answer: str, total_duration_ms: float):
        self.answer_preview = answer[:200]
        self.total_duration_ms = round(total_duration_ms, 2)


_write_lock = threading.Lock()

def persist_audit_entry(entry: AuditEntry, log_path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with _write_lock:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.__dict__) + "\n")

