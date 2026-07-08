from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import time
import uuid
from anthropic import Anthropic
from app.response_store import init_db, save_response, get_responses, get_response_by_trace
from app.config import settings
from app.datastore import DataStore
from app.governance import build_policy_chain
from app.agent import AnthropicProvider, ResearchAgent
from app.audit import AuditEntry, persist_audit_entry

RESPONSE_DB = settings.base_dir / "responses.db"
init_db(RESPONSE_DB)

app = FastAPI(
    title="NHS AI Research Assistant",
    description="An MCP-based AI research assistant for a regional NHS Research and Analytics Platform. Exposes governed access to research projects, datasets, and analytical queries via natural language.",
    version="1.0.0",
)

store = DataStore(settings.data_dir)
chain = build_policy_chain(store)
client = Anthropic(api_key=settings.anthropic_api_key)
provider = AnthropicProvider(client=client, model=settings.anthropic_model_name)
agent = ResearchAgent(provider=provider, store=store, chain=chain)

class QueryRequest(BaseModel):
    question: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"question": "Which datasets are available for diabetes research?"},
                {"question": "Which projects can alice access?"},
                {"question": "Run an analysis on DS005."},
            ]
        }
    }


class QueryResponse(BaseModel):
    answer: str
    sources: list[str]
    trace_id: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "answer": "One dataset is available for diabetes research: Primary Care Diabetes Cohort.",
                    "sources": ["DS001"],
                    "trace_id": "a1b2c3d4",
                }
            ]
        }
    }

@app.post(
    "/query",
    response_model=QueryResponse,
    summary="Ask the AI Research Assistant a question",
    description=(
        "Submit a natural language question about research projects, datasets, "
        "or analytical queries. The assistant selects and calls the appropriate "
        "MCP tools, applies governance rules (small cell suppression, role-based "
        "access, project-level access), and returns a grounded answer.\n\n"
        "Optionally pass the `X-Researcher-Id` header (e.g. `alice`, `admin`) to "
        "apply identity-aware governance. Without it, only unrestricted data is accessible."
    ),
)
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
    save_response(RESPONSE_DB, trace_id, question, answer, sources, x_researcher_id)

    return QueryResponse(answer=answer, sources=sources, trace_id=trace_id)

@app.get("/health", summary="Liveness check", 
         description="Returns service status. Used for container health checks and monitoring.",
         responses={
        200: {
            "description": "Service is healthy",
            "content": {"application/json": {"example": {"status": "ok"}}},
        }
    },
         )
def health():
    return {"status": "ok"}

@app.get("/queries", summary="List recent queries", description="Returns the most recent question/answer pairs, persisted as a source of truth independent of the audit log.",
          responses={
        200: {
            "description": "A list of recent query records",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": 1,
                            "trace_id": "a1b2c3d4",
                            "question": "Which datasets relate to diabetes?",
                            "answer": "One dataset is available for diabetes research: Primary Care Diabetes Cohort.",
                            "sources": ["DS001"],
                            "researcher": None,
                            "created_at": "2026-07-08T10:15:00+00:00",
                        }
                    ]
                }
            },
        }
    },)
def list_queries(limit: int = 10):
    return get_responses(RESPONSE_DB, limit)

    
@app.get("/queries/{trace_id}", summary="Retrieve a specific past response", description="Look up a single question/answer pair by its trace_id.",
          responses={
        200: {
            "description": "The matching query record",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "trace_id": "a1b2c3d4",
                        "question": "Which datasets relate to diabetes?",
                        "answer": "One dataset is available for diabetes research: Primary Care Diabetes Cohort.",
                        "sources": ["DS001"],
                        "researcher": None,
                        "created_at": "2026-07-08T10:15:00+00:00",
                    }
                }
            },
        },
        404: {
            "description": "No record found for this trace_id",
            "content": {"application/json": {"example": {"detail": "trace_id not found"}}},
        },
    },
          )
def get_query(trace_id: str):
    result = get_response_by_trace(RESPONSE_DB, trace_id)
    if result is None:
        raise HTTPException(status_code=404, detail="trace_id not found")
    return result
