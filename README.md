# NHS AI Research Assistant

A lightweight AI Research Assistant for a regional NHS Research and Analytics Platform.

Researchers ask natural language questions. An AI agent answers them by calling MCP tools, never by touching the underlying data directly. Every analytical result passes through a governance policy chain before it reaches the researcher, and every request is fully audited.

## Architecture Overview

The system is organised into five layers. Each layer only talks to the layer directly below it.

```
Researcher
   |
   v
[API layer]        FastAPI: POST /query, GET /health, GET /queries, GET /queries/{trace_id}
   |
   v
[Agent layer]      Claude tool-use loop: decides which tools to call, in what order,
   |                and synthesises the final answer from tool results
   v
[MCP layer]        Six tools exposing platform capabilities. The agent never
   |                bypasses this layer to touch data directly.
   v
[Governance layer] Policy chain: RoleBasedAccess -> ProjectAccess -> SmallCellSuppression
   |                Access decisions run first, content protection runs last.
   v
[Data layer]       Ingestion + repository pattern over the mock JSON files.
                    Audit log (JSONL) and response store (SQLite) as the two
                    persisted sources of truth.
```

**Cross-cutting: observability.** A `trace_id` is generated once per request and threaded through every layer, the audit log, the Langfuse trace, and the response store, so any answer can be traced end to end.

## Request Flow

1. `POST /query` arrives with a question and an optional `X-Researcher-Id` header.
2. The API layer validates the input, resolves the researcher identity (if any), and generates a `trace_id`.
3. The agent sends the question and tool schemas to Claude.
4. Claude decides which tool(s) to call. Each call is dispatched through an allowlist to the MCP layer.
5. `execute_query` results pass through the governance policy chain before returning to the agent. Every policy decision is recorded.
6. Claude synthesises a final answer from the tool results. Sources are extracted mechanically from the returned entities, never asked of the model, so they cannot be hallucinated.
7. The audit entry is finalised and persisted (JSONL). The response is persisted to the response store (SQLite). A Langfuse trace is closed, if configured.
8. `{ "answer": ..., "sources": [...], "trace_id": "..." }` is returned.

## Technology Choices

| Choice | Reasoning |
|---|---|
| Python | Primary language for AI/ML engineering, matches the role. |
| FastAPI | Async, automatic OpenAPI docs (`/docs`, `/redoc`), standard for Python AI APIs. |
| Anthropic Claude, native tool use | No heavy agent framework needed; the tool-use loop is fully visible and debuggable, which matters in a governed environment. |
| MCP Python SDK / tool schema pattern | The correct abstraction per the brief; the platform's capabilities are exposed as tools, not as a bespoke API. |
| In-memory repository over JSON | Right-sized for synthetic data; the repository pattern means swapping to a real database later touches one module. |
| SQLite response store | The one genuine write path in this exercise; gives users a retrievable history of their own questions and answers. |
| JSONL audit log | Append-only, so a crash mid-write can't corrupt prior entries; O(1) per write, unlike rewriting a JSON array on every request. |
| Langfuse | Named in the person specification; LLM-level tracing alongside the audit log. Verified against a live project, see Observability below. |

## Single Agent vs Multi Agent

**Decision: single agent.**

One Claude tool-use loop with access to all six tools. Every evaluation question is single-intent and resolves in at most two or three sequential tool calls. A single agent is easier to trace, audit, and defend line by line, properties that matter more in a governed clinical environment than raw architectural ambition.

A multi-agent design (e.g. a router delegating to specialist sub-agents) was considered and rejected for this exercise: it adds latency, more failure modes, and a harder-to-audit chain of model-to-model handoffs, for zero benefit at this problem size.

The decision rule applied: agent count should follow workload complexity, not ambition. The governance and audit layers are agent-count agnostic, so a future move to multi-agent would not require reworking either.

## Why Not LangChain

Deliberately not used. LangChain abstracts away the tool-calling loop, but that loop is exactly what this assessment is testing. Raw Anthropic tool use is about 100 lines (`app/agent.py`), fully debuggable, with no hidden prompt templates or framework machinery sitting between the code and the audit trail. In a Trusted Research Environment, fewer opaque layers means easier assurance: every model interaction is either a raw Claude API call or explicit application logic.

The `LLMProvider` interface in `app/agent.py` keeps the design open to other providers without adopting a framework: `AnthropicProvider` is the working implementation, `OpenAIProvider` is a documented stub demonstrating the seam. Adding real OpenAI support means implementing one class, not restructuring the agent loop.

## RAG: Considered and Rejected

RAG (chunking, embeddings, a vector store) was considered and deliberately not implemented for this platform's data.

The platform data is small and perfectly structured: exact IDs, exact fields, clean relationships. Direct tool-based retrieval gives exact answers with zero retrieval error. Chunking structured records would replace exact lookups with approximate semantic matches, making retrieval *less* accurate, not more. In a TRE context, deterministic retrieval is also easier to audit and govern than semantic retrieval.

**Scaling path, if this platform grew:**

- **Stage 1 (current):** in-memory indexed store behind the repository interface. Right-sized for synthetic data.
- **Stage 2 (structured growth):** swap the repository internals for Postgres with indexes and full-text search, with zero changes above the repository interface. If the dataset catalogue grew to thousands of entries, add embedding-based semantic search over dataset name/description metadata inside `search_datasets`, short metadata records, not document chunking.
- **Stage 3 (unstructured content):** if the platform later ingests unstructured content, study protocols, clinical guidelines, ethics documents, RAG with chunking and a vector store becomes the right tool, slotting in behind the same repository interface as a new retrieval path.

A related, deliberately excluded feature: external literature retrieval (e.g. PubMed) was considered, since "research assistant" naturally suggests it. It is not implemented. A Trusted Research Environment is sealed: arbitrary outbound calls from inside the environment violate isolation principles. In a real KARECTL-style deployment this would require an approved egress route or an internally mirrored index, so it is listed under Future Improvements rather than implemented here.

## Governance Design

Every `execute_query` result passes through a `PolicyChain` before reaching the agent. Each policy is a small, independent class implementing a two-method interface: `applies_to(context)` and `apply(result, context)`.

```python
PolicyChain([
    RoleBasedAccessPolicy(),     # restricted datasets require administrator access
    ProjectAccessPolicy(store),  # researchers may only analyse datasets in their assigned projects
    SmallCellSuppressionPolicy(threshold=5),  # results with fewer than 5 records are suppressed
])
```

**Ordering is deliberate:** access decisions run first, content protection runs last. If a policy denies access, the chain exits early, a denied request never reaches suppression logic, since there is no data left to protect.

**Extensibility, as required by the brief:** adding a new governance rule means writing one new class and adding it to the list above. Nothing else in the system changes. This was proven in practice during development: role-based and project-level access were added after the initial suppression policy with no changes to `PolicyChain`, the MCP layer, or the agent.

**Restricted dataset handling** lives inside `RoleBasedAccessPolicy` rather than as a separate policy, since "dataset is restricted and requester is not an administrator" is a single rule. A future enhancement could split discovery-level notices (flagging restricted status when browsing) from analysis-level blocking if that distinction becomes valuable.

## Guardrails

Guardrails are enforced in **code**, not in the prompt. The system prompt guides behaviour; the code enforces it, since a prompt can be argued with, a policy chain cannot.

- **Input:** question length capped, non-empty, treated as untrusted data.
- **Agent loop:** a tool allowlist (`dispatch_tool`) means the agent can only invoke registered tools; unknown tool names return a clean error rather than raising. A maximum iteration cap (8) prevents runaway tool-calling. Temperature 0 for determinism.
- **Output:** the governance policy chain has final say over data content, the LLM can be persuaded by a cleverly worded question, the policy chain cannot. Sources are collected mechanically from tool results, never asked of the model, so they cannot be hallucinated.
- **Failure:** tool errors return structured `{"error": ...}` dicts rather than raising exceptions into the agent loop; a request that hits the iteration cap still returns a clean response and is still audited.

**Prompt injection:** a researcher's question is untrusted input flowing into an LLM with tool access. The defence is depth, not a single filter: the tool allowlist means even a successfully "convinced" model can only call real, registered tools; the governance chain means even a successful tool call cannot bypass suppression or access rules; and the system prompt instructs the model to answer only from tool results and never fabricate data.

## Identity and Access Control

**Authentication vs authorisation.** These are different things, and this system implements only the second. `researchers.json` is an identity and permissions registry (username, role, project assignments), not a credentials store, there are no passwords or tokens. For this exercise, identity is **asserted**, not proven: an optional `X-Researcher-Id` header (e.g. `alice`, `admin`) is validated against `researchers.json` and attached to the request context.

**Without the header**, the assistant behaves normally and all 25 evaluation questions pass unchanged, unrestricted data needs no identity, exactly as a public dataset needs no login to browse.

**With the header**, two governance policies apply role-based and project-level access control:

- `RoleBasedAccessPolicy`: administrators (role contains "Administrator") may analyse restricted datasets; researchers may not.
- `ProjectAccessPolicy`: a researcher may only run analysis on datasets belonging to a project they are assigned to (matched via set intersection between the dataset's owning projects and the researcher's project list). Administrators bypass this check.

Every allow and deny decision is recorded in the audit entry with the identity, policy name, and reason, a full trail of who was denied what and why.

**Production path:** the header assertion would be replaced with real authentication (Keycloak or NHS OIDC, matching the K8TRE identity approach), with **zero changes to the governance layer**, since policies consume an identity context object, not a transport-level credential.

## Observability

Two layers, sharing one `trace_id`:

1. **Audit log (`logs/audit.jsonl`):** the platform's own compliance record. Always on, no external dependency. One JSON object per line: trace ID, question, researcher, every tool call with arguments, duration, and governance policies fired, total duration, and an answer preview.
2. **Langfuse:** LLM-level tracing for engineering teams (`app/observability.py`), one span per request with a nested tool observation per tool call. Verified working end to end against a live Langfuse Cloud project: all 25 evaluation questions traced successfully with zero regressions to answer quality or correctness. Wired with **graceful degradation**: if `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` are absent from the environment, tracing is silently skipped and the application behaves identically, also verified by running the full evaluation suite with no Langfuse keys configured. Pinned to SDK v4.13.1 in `requirements.txt`, since the Langfuse Python SDK's manual tracing API changed significantly between major versions during development (`.trace()`/`.span()` in v2 versus `.start_observation()` in v4).

A third store, the **response store** (SQLite, `responses.db`), persists every question/answer pair as a user-facing source of truth, retrievable via `GET /queries` and `GET /queries/{trace_id}`, independent of the audit log's operator-facing purpose. The schema includes a nullable `researcher` column, ready for per-researcher history once real authentication exists.

## Assumptions

1. Synthetic data is trusted input; light validation only at ingestion.
2. No authentication is implemented; identity is asserted via header for demonstration, see Identity and Access Control above.
3. `execute_query` returns pre-canned results per dataset (from `sample_query_results.json`), not a real query engine.
4. The small cell suppression threshold is 5, per the brief's example.
5. "Sources" in the API response are the IDs of entities (projects, datasets, researchers) directly returned by tool calls during the agent's reasoning.
6. Restricted datasets can be discovered and described by any researcher; only analysis (`execute_query`) is access-controlled.
7. Case-insensitive substring matching is used for keyword and role searches, so "Administrator" matches the actual data value "Platform Administrator".

## Setup Instructions

### Local

```bash
python3 -m pip install -r requirements.txt
cp .env.example .env   # then fill in ANTHROPIC_API_KEY
uvicorn app.main:app --reload
```

Interactive API docs: `http://localhost:8000/docs`

### Docker

```bash
cp .env.example .env   # then fill in ANTHROPIC_API_KEY
docker compose up --build
```

### Running tests and the evaluation harness

```bash
python3 -m pytest tests/ -v
python3 run_evals.py   # requires the app running locally on :8000
```

### CI

A GitHub Actions workflow (`.github/workflows/ci.yml`) runs the unit test suite on every push and pull request to `main`.

## Known Limitations

- Single-instance design: the audit log and response store use file/SQLite writes with a basic lock, sufficient for this exercise but not for horizontally scaled deployment.
- No authentication, identity is asserted via header, not verified.
- `search_datasets` and `search_projects` use substring keyword matching; a much larger catalogue would benefit from the semantic search step described in the RAG scaling story.
- The evaluation harness checks that all 25 questions return a 200 response with plausible content; it does not yet assert exact expected values automatically.
- `OpenAIProvider` is a structural stub, not a tested second provider.
- The Langfuse Python SDK's tracing API changed between major versions (v2's `.trace()`/`.span()` vs v4's `.start_observation()`); the integration is pinned and tested against v4.13.1 specifically.

## Future Improvements

- Replace header-based identity assertion with real authentication (Keycloak or NHS OIDC), no governance layer changes required.
- Discovery-level restricted notices as a distinct policy from analysis-level blocking.
- TRE-aware literature retrieval (e.g. PubMed) via an approved egress route or internally mirrored index.
- Postgres-backed repository for structured data growth; embedding-based semantic search over dataset metadata if the catalogue scales significantly; full RAG if unstructured content (protocols, guidelines) enters the platform.
- CI: build and push the Docker image to a registry; run the full evaluation harness against a staging deployment using a secrets-managed API key; a CD stage deploying to Kubernetes, mirroring the KARECTL/K8TRE model.
- Kubernetes manifests for production deployment (Docker and docker-compose are provided; raw K8s manifests were out of scope for this exercise's time budget).