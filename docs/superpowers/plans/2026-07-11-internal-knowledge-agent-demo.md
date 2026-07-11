# Internal Knowledge Agent Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Dockerized internal knowledge-base Agent demo with authenticated users, document ACLs, permission-aware RAG, an authorized salary data tool, cited answers, and a React UI.

**Architecture:** FastAPI owns identity, authorization, API contracts, and trusted user context. A LangGraph workflow routes questions to ACL-filtered document retrieval and/or an authorized internal-data tool, then produces grounded answers through LangChain model abstractions. PostgreSQL with pgvector stores application data, document chunks, embeddings, audit events, and graph checkpoints; React provides login, chat, citations, and admin ingestion screens.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16 + pgvector, LangChain 1.x, LangGraph 1.x, React 18, TypeScript, Vite, Vitest, pytest, Docker Compose.

## Global Constraints

- Work directly on `main`; do not create feature branches.
- Keep the demo runnable with one command: `docker compose up --build`.
- Authorization is deterministic backend code; the model never grants permissions.
- Apply document ACL filters before vector ranking and verify returned document IDs again afterward.
- Salary access is self-only except for `hr` and `admin`; denied requests never expose salary values to the model.
- Knowledge answers include document title, page or section, and quoted source snippets.
- When evidence is absent, low-confidence, or unauthorized, answer: `无法根据您当前有权限访问的信息回答该问题。`
- Support PDF, DOCX, Markdown, and TXT; scanned-document OCR is out of scope.
- Treat ingested text as untrusted data, not instructions.
- Keep model and embedding names configurable through environment variables.
- Never put secrets in frontend bundles, committed files, logs, or model prompts.

---

## Target File Map

```text
backend/
├── pyproject.toml                         # Python dependencies and test configuration
├── alembic.ini                            # Migration runner configuration
├── alembic/env.py                         # SQLAlchemy metadata wiring
├── alembic/versions/0001_initial.py       # pgvector extension and core tables
├── app/main.py                            # FastAPI application and router assembly
├── app/config.py                          # Environment-backed settings
├── app/db.py                              # Engine/session lifecycle
├── app/models.py                          # SQLAlchemy tables and enums
├── app/schemas.py                         # Shared API schemas
├── app/auth/{passwords,tokens,dependencies}.py
├── app/policies/{documents,salaries}.py   # Pure deterministic authorization rules
├── app/retrieval/{ingest,search}.py       # Parse/chunk/embed and ACL vector search
├── app/ingestion/{__main__,worker}.py     # Polling ingestion process
├── app/tools/salary.py                    # Authorized structured-data tool
├── app/graph/{state,workflow}.py           # LangGraph state and conditional workflow
├── app/api/{auth,chat,documents,threads}.py
├── app/seed.py                            # Demo users, roles, salaries, and sample docs
└── tests/                                 # Unit/API/integration tests
frontend/
├── package.json                           # React/Vite/Vitest dependencies
├── vite.config.ts                         # Build and proxy configuration
├── src/api/client.ts                      # Typed backend client
├── src/auth/AuthContext.tsx               # Session state
├── src/pages/{Login,Chat,Documents}.tsx   # Three demo surfaces
├── src/components/{Shell,Citations}.tsx   # Shared UI
├── src/styles.css                         # Responsive visual system
└── src/**/*.test.tsx                      # UI behavior tests
docker-compose.yml                         # frontend/backend/ingest/postgres
.env.example                               # Safe configuration template
documents/                                 # Seed knowledge documents
README.md                                  # Setup, demo accounts, verification
```

### Task 1: Runnable project foundation

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/test_health.py`
- Create: `backend/Dockerfile`
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/Dockerfile`
- Create: `frontend/nginx.conf`
- Create: `docker-compose.yml`
- Create: `.env.example`

**Interfaces:**
- Produces: `GET /health -> {"status": "ok"}` and four Compose services named `frontend`, `backend`, `ingest`, and `postgres`.
- Consumes: no earlier application code.

- [ ] **Step 1: Write the failing backend health test**

```python
from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run the focused test and confirm the missing application failure**

Run: `cd backend && python -m pytest tests/test_health.py -q`
Expected: FAIL because `app.main` does not exist.

- [ ] **Step 3: Add the minimal FastAPI app, settings, package metadata, and container**

```python
# backend/app/main.py
from fastapi import FastAPI

app = FastAPI(title="Internal Knowledge Agent")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

Declare Python 3.12 and explicit runtime/test dependencies in `backend/pyproject.toml`. The backend container runs `uvicorn app.main:app --host 0.0.0.0 --port 8000`.

- [ ] **Step 4: Add the minimal React shell and production Nginx container**

```tsx
// frontend/src/App.tsx
export function App() {
  return <main><h1>Internal Knowledge Agent</h1></main>;
}
```

The Vite dev configuration proxies `/api` and `/health` to `backend:8000`; the production Nginx configuration serves the SPA and proxies the same paths.

- [ ] **Step 5: Add Compose services and safe environment defaults**

Use `pgvector/pgvector:pg16`, a named database volume, a shared document volume for `backend` and `ingest`, dependency health checks, and no published PostgreSQL port. `.env.example` includes placeholders for `OPENAI_API_KEY`, `JWT_SECRET`, `CHAT_MODEL`, and `EMBEDDING_MODEL` but no real values.

- [ ] **Step 6: Verify foundation**

Run: `cd backend && python -m pytest tests/test_health.py -q`
Expected: `1 passed`.

Run: `docker compose config`
Expected: exit 0 and all four service names present.

- [ ] **Step 7: Commit foundation**

```bash
git add .env.example docker-compose.yml backend frontend
git commit -m "Build runnable application foundation"
```

### Task 2: Database schema, migrations, and demo identities

**Files:**
- Create: `backend/app/db.py`
- Create: `backend/app/models.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0001_initial.py`
- Create: `backend/app/seed.py`
- Create: `backend/tests/test_models.py`
- Create: `documents/employee-handbook.md`
- Create: `documents/engineering-guide.md`
- Create: `documents/hr-compensation-policy.md`

**Interfaces:**
- Produces: `get_session()`, enums `SubjectType` and `DocumentStatus`, and models `User`, `Role`, `UserRole`, `Document`, `DocumentPermission`, `DocumentChunk`, `Salary`, `AuditLog`, `ThreadOwner`.
- Produces demo users: `alice.programmer`, `helen.hr`, `andy.admin`, all with password `demo-password` documented as non-production credentials.

- [ ] **Step 1: Write schema behavior tests**

```python
def test_document_status_values() -> None:
    assert {item.value for item in DocumentStatus} == {
        "pending", "processing", "ready", "failed"
    }


def test_subject_type_values() -> None:
    assert {item.value for item in SubjectType} == {
        "authenticated", "user", "role", "department"
    }
```

- [ ] **Step 2: Run tests and confirm missing model failures**

Run: `cd backend && python -m pytest tests/test_models.py -q`
Expected: FAIL importing `app.models`.

- [ ] **Step 3: Implement focused SQLAlchemy models and migration**

Use UUID primary keys for user/document entities, a composite unique constraint on document permissions, `Vector(settings.embedding_dimensions)` for chunk embeddings, and explicit foreign-key cascade behavior. Migration `0001_initial` first executes `CREATE EXTENSION IF NOT EXISTS vector` and then creates all tables and indexes.

- [ ] **Step 4: Add idempotent seed data**

```python
DEMO_USERS = (
    ("alice.programmer", "engineering", ("programmer",)),
    ("helen.hr", "people", ("hr",)),
    ("andy.admin", "operations", ("admin",)),
)
```

Seed salaries for all three users and register the sample documents with ACLs: handbook=`authenticated`, engineering guide=`department:engineering`, compensation policy=`role:hr` plus `role:admin`.

- [ ] **Step 5: Verify migration and seed idempotency**

Run: `docker compose up -d postgres && docker compose run --rm backend alembic upgrade head`
Expected: exit 0 with pgvector extension and all core tables created.

Run twice: `docker compose run --rm backend python -m app.seed`
Expected: both runs exit 0; row counts do not increase on the second run.

- [ ] **Step 6: Commit database foundation**

```bash
git add backend/app/db.py backend/app/models.py backend/app/seed.py backend/alembic.ini backend/alembic documents backend/tests/test_models.py
git commit -m "Add database schema and demo data"
```

### Task 3: Authentication and deterministic authorization policies

**Files:**
- Create: `backend/app/auth/passwords.py`
- Create: `backend/app/auth/tokens.py`
- Create: `backend/app/auth/dependencies.py`
- Create: `backend/app/policies/documents.py`
- Create: `backend/app/policies/salaries.py`
- Create: `backend/app/schemas.py`
- Create: `backend/app/api/auth.py`
- Create: `backend/tests/test_auth.py`
- Create: `backend/tests/test_policies.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Produces: `hash_password(str) -> str`, `verify_password(str, str) -> bool`, `create_access_token(UUID) -> str`, `get_current_user() -> User`.
- Produces: `SalaryDecision(allowed: bool, reason: str)` and `can_read_salary(actor, target) -> SalaryDecision`.
- Produces: `document_access_clause(user) -> ColumnElement[bool]` for use inside retrieval SQL.

- [ ] **Step 1: Write failing policy tests**

```python
def test_programmer_can_read_own_salary(programmer) -> None:
    assert can_read_salary(programmer, programmer).allowed is True


def test_programmer_cannot_read_another_salary(programmer, hr_user) -> None:
    decision = can_read_salary(programmer, hr_user)
    assert decision.allowed is False
    assert decision.reason == "salary_access_denied"


def test_hr_can_read_another_salary(hr_user, programmer) -> None:
    assert can_read_salary(hr_user, programmer).allowed is True
```

- [ ] **Step 2: Run tests and confirm missing policy failures**

Run: `cd backend && python -m pytest tests/test_auth.py tests/test_policies.py -q`
Expected: FAIL because authentication and policy modules do not exist.

- [ ] **Step 3: Implement password hashing, JWT, current-user loading, and policies**

JWT contains only `sub`, `iat`, and `exp`. `get_current_user` reloads the active user, department, and roles from PostgreSQL for every request. `can_read_salary` allows same-user access or roles `hr`/`admin`; it never inspects model output.

- [ ] **Step 4: Implement login and current-user endpoints**

```text
POST /api/auth/login {username, password} -> {access_token, token_type}
GET  /api/auth/me    Bearer token         -> {id, username, department, roles}
```

Invalid credentials always return the same 401 response. Disabled users are rejected even with a valid unexpired token.

- [ ] **Step 5: Verify authentication and policies**

Run: `cd backend && python -m pytest tests/test_auth.py tests/test_policies.py -q`
Expected: all tests pass, including token expiry and disabled-user cases.

- [ ] **Step 6: Commit identity and policy layer**

```bash
git add backend/app/auth backend/app/policies backend/app/schemas.py backend/app/api/auth.py backend/app/main.py backend/tests
git commit -m "Enforce authentication and resource policies"
```

### Task 4: Authorized salary tool and audit trail

**Files:**
- Create: `backend/app/tools/salary.py`
- Create: `backend/app/audit.py`
- Create: `backend/tests/test_salary_tool.py`

**Interfaces:**
- Consumes: `can_read_salary(actor, target)` and SQLAlchemy models from Tasks 2–3.
- Produces: `get_salary(actor: User, target_username: str, session: Session) -> SalaryToolResult` where denied results contain no amount or target existence details.

- [ ] **Step 1: Write failing salary-tool tests**

```python
def test_denied_salary_result_never_contains_amount(session, programmer, hr_user) -> None:
    result = get_salary(programmer, hr_user.username, session)
    assert result.allowed is False
    assert result.amount is None
    assert result.message == SAFE_DENIAL_MESSAGE
```

- [ ] **Step 2: Run the focused test and confirm failure**

Run: `cd backend && python -m pytest tests/test_salary_tool.py -q`
Expected: FAIL importing `app.tools.salary`.

- [ ] **Step 3: Implement the tool with authorization before data access**

Resolve the target identity, run `can_read_salary`, and query the salary table only after an allow decision. Write an audit row for allowed, denied, missing-self-data, and internal-error outcomes. Return a typed result safe to place in model context.

- [ ] **Step 4: Verify leakage and audit behavior**

Run: `cd backend && python -m pytest tests/test_salary_tool.py -q`
Expected: all tests pass; denied tests assert that salary-query execution was not called.

- [ ] **Step 5: Commit the authorized tool**

```bash
git add backend/app/tools backend/app/audit.py backend/tests/test_salary_tool.py
git commit -m "Add authorized salary data tool"
```

### Task 5: Document ingestion pipeline and worker

**Files:**
- Create: `backend/app/retrieval/ingest.py`
- Create: `backend/app/ingestion/worker.py`
- Create: `backend/app/ingestion/__main__.py`
- Create: `backend/tests/test_ingest.py`

**Interfaces:**
- Produces: `parse_document(path) -> list[ParsedSection]`, `chunk_sections(sections, max_tokens=700, overlap_tokens=100) -> list[ChunkDraft]`, `ingest_document(document_id, session, embedder) -> None`.
- Produces: worker command `python -m app.ingestion` supporting `--once` for tests and manual runs.

- [ ] **Step 1: Write parser and chunking tests using temporary Markdown/TXT files**

```python
def test_markdown_sections_keep_heading_metadata(tmp_path) -> None:
    path = tmp_path / "guide.md"
    path.write_text("# Deploy\nUse Docker.\n## Rollback\nRestore backup.")
    sections = parse_document(path)
    assert sections[0].section == "Deploy"
    assert sections[1].section == "Rollback"
```

- [ ] **Step 2: Run focused tests and confirm missing pipeline failure**

Run: `cd backend && python -m pytest tests/test_ingest.py -q`
Expected: FAIL importing `app.retrieval.ingest`.

- [ ] **Step 3: Implement safe parsers, chunking, and checksum behavior**

PDF sections include page numbers from pypdf; DOCX sections follow heading paragraphs; Markdown follows headings; TXT uses paragraph groups. Reject unsupported extensions and oversized files with typed errors. Never execute macros, links, scripts, or document instructions.

- [ ] **Step 4: Implement transactional embedding and worker status transitions**

Transition `pending -> processing -> ready`; on exception set `failed` plus a sanitized error. Generate all new chunks before deleting old ones, then replace them in one transaction. The polling worker locks one pending document with `FOR UPDATE SKIP LOCKED`.

- [ ] **Step 5: Verify parsers, retries, and state transitions**

Run: `cd backend && python -m pytest tests/test_ingest.py -q`
Expected: all parser, chunk overlap, duplicate checksum, success, and failure-state tests pass.

- [ ] **Step 6: Commit ingestion pipeline**

```bash
git add backend/app/retrieval/ingest.py backend/app/ingestion backend/tests/test_ingest.py
git commit -m "Build document ingestion pipeline"
```

### Task 6: ACL-filtered semantic retrieval

**Files:**
- Create: `backend/app/retrieval/search.py`
- Create: `backend/tests/test_retrieval.py`

**Interfaces:**
- Consumes: current `User`, `document_access_clause`, document/chunk models, and configured embedder.
- Produces: `search_documents(query: str, user: User, session: Session, embedder, limit: int = 5) -> list[RetrievedChunk]`.

- [ ] **Step 1: Write failing retrieval security tests**

```python
def test_programmer_search_never_returns_hr_document(retriever, programmer) -> None:
    results = retriever.search("薪酬等级", programmer)
    assert all(item.document_title != "HR 薪酬制度" for item in results)


def test_search_returns_citation_metadata(retriever, programmer) -> None:
    result = retriever.search("工程发布流程", programmer)[0]
    assert result.document_title
    assert result.source_locator
    assert result.snippet
```

- [ ] **Step 2: Run the focused tests and confirm missing search failure**

Run: `cd backend && python -m pytest tests/test_retrieval.py -q`
Expected: FAIL importing `app.retrieval.search`.

- [ ] **Step 3: Implement one-query ACL filtering plus vector ranking**

The SQL query joins chunks to ready documents, applies an `EXISTS` ACL predicate for authenticated/user/role/department subjects, and only then orders by cosine distance. Map results to immutable `RetrievedChunk` values and perform a defense-in-depth document-access assertion before returning.

- [ ] **Step 4: Verify authorization boundaries and empty results**

Run: `cd backend && python -m pytest tests/test_retrieval.py -q`
Expected: all tests pass; unauthorized documents never appear even when their vectors rank highest globally.

- [ ] **Step 5: Commit retrieval**

```bash
git add backend/app/retrieval/search.py backend/tests/test_retrieval.py
git commit -m "Add permission-aware semantic retrieval"
```

### Task 7: LangGraph workflow, chat API, and thread isolation

**Files:**
- Create: `backend/app/graph/state.py`
- Create: `backend/app/graph/workflow.py`
- Create: `backend/app/api/chat.py`
- Create: `backend/app/api/threads.py`
- Create: `backend/tests/test_graph.py`
- Create: `backend/tests/test_chat_api.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Produces: `AgentState` with messages, route, document evidence, tool evidence, citations, answer, actor_id, and thread_id.
- Produces: compiled graph with nodes `route_query`, `retrieve_documents`, `query_employee_data`, `compose_answer`, `verify_answer`, and `audit_run`.
- Produces: `POST /api/chat` and user-owned thread listing.

- [ ] **Step 1: Write deterministic graph-routing and refusal tests with fake models**

```python
def test_empty_evidence_uses_safe_denial(fake_graph, programmer_context) -> None:
    result = fake_graph.invoke({"message": "告诉我 HR 薪资", **programmer_context})
    assert result["answer"] == SAFE_DENIAL_MESSAGE
    assert result["citations"] == []
```

- [ ] **Step 2: Run graph/API tests and confirm missing workflow failures**

Run: `cd backend && python -m pytest tests/test_graph.py tests/test_chat_api.py -q`
Expected: FAIL importing graph and chat modules.

- [ ] **Step 3: Implement the conditional graph with injected dependencies**

Use structured route output restricted to `documents`, `employee_data`, or `mixed`. Nodes call Tasks 4 and 6 using the trusted actor loaded by FastAPI. The answer prompt separates system instructions from `<evidence>` blocks, labels document text as untrusted, and requires citations only from provided evidence.

- [ ] **Step 4: Implement answer verification and safe refusal**

If no allowed evidence exists, if retrieval scores exceed the configured distance threshold, or if citations reference unknown evidence IDs, replace the response with `SAFE_DENIAL_MESSAGE`. Never expose internal denial reasons or hidden resource names.

- [ ] **Step 5: Implement chat and thread ownership endpoints**

Associate every `thread_id` with the authenticated user. Reject attempts to reuse another user's thread with 404. Return `{thread_id, answer, citations, activity}`; activity contains safe labels such as `searched_documents` and `queried_employee_data`, never chain-of-thought.

- [ ] **Step 6: Verify graph and API security boundaries**

Run: `cd backend && python -m pytest tests/test_graph.py tests/test_chat_api.py -q`
Expected: routing, tool error, citation, safe refusal, and cross-user thread tests all pass.

- [ ] **Step 7: Commit Agent runtime**

```bash
git add backend/app/graph backend/app/api/chat.py backend/app/api/threads.py backend/app/main.py backend/tests
git commit -m "Add controlled knowledge agent workflow"
```

### Task 8: Admin document API

**Files:**
- Create: `backend/app/api/documents.py`
- Create: `backend/tests/test_documents_api.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Produces: `POST /api/admin/documents`, `GET /api/admin/documents`, and `POST /api/admin/documents/{id}/retry`.
- Consumes: document models, ACL subject types, shared document volume, and authenticated admin dependency.

- [ ] **Step 1: Write failing upload authorization and validation tests**

```python
def test_programmer_cannot_upload_document(programmer_client) -> None:
    response = programmer_client.post("/api/admin/documents", files={"file": ("x.md", b"# x")})
    assert response.status_code == 403


def test_admin_upload_creates_pending_document(admin_client) -> None:
    response = admin_client.post(
        "/api/admin/documents",
        files={"file": ("guide.md", b"# Guide\nSafe content")},
        data={"title": "Guide", "subjects": '[{"type":"authenticated","id":null}]'},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "pending"
```

- [ ] **Step 2: Run tests and confirm missing route failure**

Run: `cd backend && python -m pytest tests/test_documents_api.py -q`
Expected: FAIL because document routes are absent.

- [ ] **Step 3: Implement admin-only upload/list/retry routes**

Stream uploads to a generated server-side filename, enforce extension and byte limit, compute checksum, insert ACL rows transactionally, and never trust client paths. Retry only `failed` documents and clear their sanitized error message.

- [ ] **Step 4: Verify API behavior**

Run: `cd backend && python -m pytest tests/test_documents_api.py -q`
Expected: role enforcement, duplicate detection, size/format rejection, status listing, and retry cases pass.

- [ ] **Step 5: Commit admin API**

```bash
git add backend/app/api/documents.py backend/app/main.py backend/tests/test_documents_api.py
git commit -m "Add secure document administration API"
```

### Task 9: React login, chat, citations, and document administration

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/auth/AuthContext.tsx`
- Create: `frontend/src/components/Shell.tsx`
- Create: `frontend/src/components/Citations.tsx`
- Create: `frontend/src/pages/Login.tsx`
- Create: `frontend/src/pages/Chat.tsx`
- Create: `frontend/src/pages/Documents.tsx`
- Create: `frontend/src/styles.css`
- Create: `frontend/src/pages/Login.test.tsx`
- Create: `frontend/src/pages/Chat.test.tsx`
- Create: `frontend/src/pages/Documents.test.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: Tasks 3, 7, and 8 HTTP contracts.
- Produces: authenticated SPA with role-aware navigation, cited chat responses, safe activity labels, and admin ingestion status.

- [ ] **Step 1: Write failing UI behavior tests**

```tsx
it("renders citations returned by chat", async () => {
  render(<Chat />);
  await userEvent.type(screen.getByLabelText("问题"), "发布流程是什么？");
  await userEvent.click(screen.getByRole("button", { name: "发送" }));
  expect(await screen.findByText("工程指南 · 发布流程")).toBeVisible();
});
```

- [ ] **Step 2: Run frontend tests and confirm missing component failures**

Run: `cd frontend && npm test -- --run`
Expected: FAIL because pages, API client, and test setup are missing.

- [ ] **Step 3: Implement typed API client and authentication context**

Keep the access token in memory plus sessionStorage for Demo convenience, clear it on 401, and never log it. Load `/api/auth/me` before rendering protected routes.

- [ ] **Step 4: Implement the three pages and shared components**

Use the visual language established in `docs/design.html`: warm paper background, forest surfaces, orange signal color, editorial typography, compact evidence cards, visible keyboard focus, reduced-motion support, and responsive navigation. Show the Documents route only to admins.

- [ ] **Step 5: Verify UI tests and production build**

Run: `cd frontend && npm test -- --run`
Expected: all Login, Chat, Citation, and admin-navigation tests pass.

Run: `cd frontend && npm run build`
Expected: TypeScript and Vite build exit 0.

- [ ] **Step 6: Commit frontend**

```bash
git add frontend
git commit -m "Build internal knowledge agent interface"
```

### Task 10: End-to-end Docker demo, documentation, and final verification

**Files:**
- Create: `backend/tests/integration/test_demo_flows.py`
- Modify: `README.md`
- Modify: `docker-compose.yml`
- Modify: `.env.example`

**Interfaces:**
- Consumes: the complete application.
- Produces: documented startup, demo accounts, sample questions, reset procedure, and verified acceptance flows.

- [ ] **Step 1: Write acceptance tests for the highest-risk flows**

```python
def test_programmer_cannot_retrieve_hr_chunks(live_clients) -> None:
    answer = live_clients.programmer.ask("HR 薪酬等级是什么？")
    assert answer.text == SAFE_DENIAL_MESSAGE
    assert answer.citations == []


def test_programmer_can_read_self_but_not_other_salary(live_clients) -> None:
    assert "CNY" in live_clients.programmer.ask("我的薪资是多少？").text
    denied = live_clients.programmer.ask("Helen 的薪资是多少？")
    assert denied.text == SAFE_DENIAL_MESSAGE
```

- [ ] **Step 2: Run the full backend and frontend suites**

Run: `cd backend && python -m pytest -q`
Expected: all tests pass.

Run: `cd frontend && npm test -- --run && npm run build`
Expected: all tests pass and production build succeeds.

- [ ] **Step 3: Run the containerized acceptance path**

Run: `docker compose down -v && docker compose up --build -d`
Expected: all services become healthy.

Run: `docker compose run --rm backend alembic upgrade head && docker compose run --rm backend python -m app.seed`
Expected: migrations and seed complete successfully.

Run: `docker compose run --rm ingest python -m app.ingestion --once`
Expected: all three sample documents reach `ready`.

- [ ] **Step 4: Verify browser workflows**

Open `http://localhost:3000`; validate login as programmer and admin, cited document answers, safe salary denial, admin upload status, responsive layout at 390px, and no browser console errors.

- [ ] **Step 5: Finish README**

Document prerequisites, exact startup commands, environment variables, demo credentials, sample allowed/denied questions, architecture link, reset commands, security limitations, and how to substitute a different OpenAI-compatible model provider.

- [ ] **Step 6: Run final repository checks**

Run: `git diff --check && git status --short`
Expected: no whitespace errors; only intentional README/config/test changes before commit.

- [ ] **Step 7: Commit final Demo verification**

```bash
git add README.md .env.example docker-compose.yml backend/tests/integration
git commit -m "Document and verify the complete demo"
git push origin main
```

## Plan Self-Review

- Spec coverage: every HTML design section maps to at least one task, including scope, workflow, ingestion, ACL, schema, API, UI, Docker, risks, tests, and acceptance criteria.
- Security coverage: authorization is tested independently from the model; retrieval and salary flows both fail closed; thread ownership and prompt-injection boundaries are explicit.
- Type consistency: policy, retrieval, salary-tool, graph, and API interfaces are defined before their consumers.
- Scope control: OCR, SSO, enterprise IAM, high availability, model hosting, and online document editing remain excluded.
- Placeholder scan: every implementation and error-handling step is concrete and executable.
