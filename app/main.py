from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import time
import uuid
from anthropic import Anthropic

from app.config import settings
from app.data_store import DataStore
from app.governance import build_policy_chain
from app.agent import AnthropicProvider, ResearchAgent
from app.audit import AuditEntry, persist_audit_entry

app = FastAPI(title="NHS AI Research Assistant")

store = DataStore(settings.data_dir)
chain = build_policy_chain(store)
client = Anthropic(api_key=settings.anthropic_api_key)
provider = AnthropicProvider(client=client, model=settings.anthropic_model_name)
agent = ResearchAgent(provider=provider, store=store, chain=chain)

class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[str]
    trace_id: str

@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest, x_researcher_id: str | None = Header(default=None)):
    question = request.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    if len(question) > 2000:
        raise HTTPException(status_code=400, detail="Question is too long.")

    researcher = None
    if x_researcher_id is not None:
        researcher = store.get_researcher_by_username(x_researcher_id)
        if researcher is None:
            raise HTTPException(status_code=400, detail=f"Unknown researcher id: {x_researcher_id}")

    trace_id = str(uuid.uuid4())
    entry = AuditEntry(trace_id=trace_id, question=question, researcher=x_researcher_id)

    start = time.perf_counter()
    answer, sources = agent.run(question, researcher, trace_id, entry)
    total_duration_ms = (time.perf_counter() - start) * 1000

    entry.finalise(answer, total_duration_ms)
    persist_audit_entry(entry, settings.logs_dir / "audit.jsonl")

    return QueryResponse(answer=answer, sources=sources, trace_id=trace_id)

@app.get("/health")
def health():
    return {"status": "ok"}