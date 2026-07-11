# Document Preview and Retrieval Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an admin-only document-content preview, fix false denials from the local embedding index, and improve chat keyboard behavior.

**Architecture:** Extend the existing admin API with an on-demand detail response instead of enlarging the list payload. Version the local hash index as `local-hash-v2`, include title and section in embedded text, automatically requeue stale READY documents, and inject the calibrated `0.72` retrieval distance through settings. Keep the current React page architecture, adding a focused preview drawer component and textarea keyboard handling.

**Tech Stack:** FastAPI, SQLAlchemy, LangChain/LangGraph, PostgreSQL/pgvector, React, TypeScript, Vitest, Docker Compose

## Global Constraints

- Work directly on `main`, as requested by the user.
- Preserve SQL ACL filtering before pgvector ordering and limiting.
- Keep the document detail endpoint admin-only and never return `source_path`, checksum, or embeddings.
- Use `local-hash-v2` as the exact chunk metadata index version.
- Use `RETRIEVAL_MAX_DISTANCE=0.72` as the default local retrieval cutoff.
- Preview only Ingest output; do not add raw PDF/DOCX rendering or downloads.
- Enter sends, Shift+Enter inserts a newline, and composition Enter does not send.

---

### Task 1: Version and recalibrate the local document index

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/retrieval/ingest.py`
- Modify: `backend/app/ingestion/worker.py`
- Modify: `backend/app/api/chat.py`
- Modify: `.env.example`
- Test: `backend/tests/test_ingest.py`
- Create: `backend/tests/test_ingestion_worker.py`
- Modify: `backend/tests/test_embeddings.py`
- Modify: `backend/tests/test_claude_runtime.py`

**Interfaces:**
- Produces: `INDEX_VERSION = "local-hash-v2"`
- Produces: `build_embedding_text(title: str, draft: ChunkDraft) -> str`
- Produces: `mark_stale_documents_pending(session: Session) -> int`
- Produces: `Settings.retrieval_max_distance: float = 0.72`
- Consumes: existing `ingest_document`, `LocalHashEmbeddings`, `DocumentChunk.metadata`, and `KnowledgeAgent(max_distance=...)`

- [x] **Step 1: Add failing index-input and version tests**

In `backend/tests/test_ingest.py`, make `FakeEmbedder` record received texts and assert that ingesting title `Guide`, section `Deploy`, and content `Use the release checklist.` sends exactly:

```python
"Guide\nDeploy\nUse the release checklist."
```

Also assert the created chunk contains:

```python
{"source_path": "guide.md", "embedding_version": "local-hash-v2"}
```

Run:

```bash
backend/.venv/bin/pytest -q backend/tests/test_ingest.py
```

Expected: FAIL because ingest currently embeds only `draft.content` and omits `embedding_version`.

- [x] **Step 2: Implement metadata-aware embedding input**

In `backend/app/retrieval/ingest.py`, add:

```python
INDEX_VERSION = "local-hash-v2"


def build_embedding_text(title: str, draft: ChunkDraft) -> str:
    return "\n".join(
        value for value in (title.strip(), (draft.section or "").strip(), draft.content)
        if value
    )
```

Use `build_embedding_text(document.title, draft)` for `embed_documents`, and add `"embedding_version": INDEX_VERSION` to each chunk metadata object.

Run the focused ingest tests and expect PASS.

- [x] **Step 3: Add failing stale-index worker tests**

Create `backend/tests/test_ingestion_worker.py` with tests that compile or execute the stale-document update and prove:

- a READY document with no `local-hash-v2` chunk is moved to PENDING;
- a READY document containing a `local-hash-v2` chunk is not moved;
- PENDING documents remain eligible for the existing claim path.

Run:

```bash
backend/.venv/bin/pytest -q backend/tests/test_ingestion_worker.py
```

Expected: FAIL because `mark_stale_documents_pending` does not exist.

- [x] **Step 4: Implement automatic stale-index requeue**

Add `mark_stale_documents_pending(session)` using a SQLAlchemy correlated `exists` query. It must update READY documents for which no chunk has metadata key `embedding_version` equal to `local-hash-v2`, commit before polling, and return the affected row count. Invoke it once when `run_worker` starts, before the polling loop.

Do not requeue FAILED documents. Keep the existing `claim_pending_document` transaction and `skip_locked` behavior.

- [x] **Step 5: Add failing calibrated-distance and configuration tests**

Extend `backend/tests/test_embeddings.py` with the exact title/section/body composites from the seeded employee and engineering documents. Assert cosine distances for these pairs are at most `0.72`:

```text
公司的核心协作时间是什么？ -> 员工手册 / 工作时间
工程发布流程是什么？ -> 工程团队指南 / 发布流程
```

Assert unrelated cross-document pairs remain greater than `0.72`.

Extend `backend/tests/test_claude_runtime.py` to assert `RuntimeServices(Settings(..., retrieval_max_distance=0.72)).max_distance == 0.72`.

Run both focused files and expect the runtime assertion to fail before implementation.

- [x] **Step 6: Inject the retrieval cutoff through settings**

Add this field in `backend/app/config.py`:

```python
retrieval_max_distance: float = 0.72
```

Store it on `RuntimeServices` and pass it into `KnowledgeAgent(max_distance=services.max_distance)` in `backend/app/api/chat.py`. Add `RETRIEVAL_MAX_DISTANCE=0.72` to `.env.example`.

Run:

```bash
backend/.venv/bin/pytest -q backend/tests/test_ingest.py backend/tests/test_ingestion_worker.py backend/tests/test_embeddings.py backend/tests/test_claude_runtime.py backend/tests/test_graph.py
```

Expected: all focused tests pass.

- [x] **Step 7: Commit the local-index fix**

```bash
git add .env.example backend/app/config.py backend/app/retrieval/ingest.py backend/app/ingestion/worker.py backend/app/api/chat.py backend/tests/test_ingest.py backend/tests/test_ingestion_worker.py backend/tests/test_embeddings.py backend/tests/test_claude_runtime.py
git commit -m "Fix local document retrieval indexing"
```

---

### Task 2: Add the admin-only document detail API

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/api/documents.py`
- Modify: `backend/tests/test_documents_api.py`

**Interfaces:**
- Produces: `DocumentPermissionResponse(subject_type: str, subject_id: str)`
- Produces: `DocumentChunkResponse(chunk_index: int, section: str | None, page_number: int | None, content: str)`
- Produces: `DocumentDetailResponse` extending the list fields with timestamps, permissions, `chunk_count`, and chunks
- Produces: `GET /api/admin/documents/{document_id}`

- [x] **Step 1: Write failing detail endpoint tests**

Add tests for:

- admin receives title, READY status, sorted chunks, permissions, and `chunk_count`;
- response omits `source_path`, `checksum`, and `embedding`;
- programmer receives `403`;
- missing document receives `404`.

Use FastAPI dependency overrides consistent with the existing upload tests.

Run:

```bash
backend/.venv/bin/pytest -q backend/tests/test_documents_api.py
```

Expected: FAIL with `405` or `404` because the GET detail route is absent.

- [x] **Step 2: Define detail response schemas**

Add Pydantic response models using strings for enum values and timezone-aware datetimes. Keep `DocumentResponse` unchanged so list payloads remain small.

- [x] **Step 3: Implement the detail route**

Load the document with `selectinload(Document.permissions)` and `selectinload(Document.chunks)`. Return permissions in deterministic `(subject_type, subject_id)` order and chunks by `chunk_index`. Raise `HTTPException(404, "Document not found")` when absent.

Run the focused tests and expect PASS.

- [x] **Step 4: Commit the API**

```bash
git add backend/app/schemas.py backend/app/api/documents.py backend/tests/test_documents_api.py
git commit -m "Add admin document detail API"
```

---

### Task 3: Build the document preview drawer

**Required skill before implementation:** `frontend-design` for visual integration with the existing interface.

**Files:**
- Create: `frontend/src/components/DocumentPreview.tsx`
- Modify: `frontend/src/pages/Documents.tsx`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/pages/Documents.test.tsx`

**Interfaces:**
- Produces: `DocumentDetail`, `DocumentPermission`, and `DocumentChunk` TypeScript types
- Produces: `api.document(token: string, id: string): Promise<DocumentDetail>`
- Produces: `DocumentPreview({ detail, loading, error, onClose })`
- Consumes: existing document list and authentication token

- [x] **Step 1: Write failing preview interaction tests**

Mock `api.documents` and `api.document`. Assert clicking the `工程指南` row requests its ID and shows:

- dialog accessible name `工程指南`;
- permission `department: engineering`;
- section `发布流程`;
- extracted body text;
- close button behavior.

Add separate assertions for loading, request error, and an empty chunks array.

Run:

```bash
pnpm --dir frontend test -- --run src/pages/Documents.test.tsx
```

Expected: FAIL because rows are not interactive and there is no preview.

- [x] **Step 2: Add client types and the detail request**

Define exact API response shapes matching Task 2 and add:

```typescript
document: (token: string, id: string) =>
  request<DocumentDetail>(`/api/admin/documents/${id}`, {}, token)
```

- [x] **Step 3: Implement the accessible drawer component**

Create a right-side `role="dialog"` drawer with `aria-modal="true"`, an accessible title, status, permissions, chunk count, ordered chunk cards, loading/error/empty states, close button, and Escape handling. Do not render raw HTML from document content.

- [x] **Step 4: Make document rows interactive**

Track selected ID, detail, loading, and error in `Documents.tsx`. Fetch details only after row activation. Use a real button inside each row or equivalent keyboard-safe semantics; preserve retry behavior for FAILED rows without opening the drawer accidentally.

- [x] **Step 5: Style and verify the drawer**

Add a backdrop, fixed right panel, scrollable content, responsive full-width behavior below `800px`, and focus/hover states consistent with the current forest/paper visual system.

Run:

```bash
pnpm --dir frontend test -- --run src/pages/Documents.test.tsx
pnpm --dir frontend build
```

Expected: focused tests and TypeScript production build pass.

- [x] **Step 6: Commit the preview UI**

```bash
git add frontend/src/components/DocumentPreview.tsx frontend/src/pages/Documents.tsx frontend/src/api/client.ts frontend/src/styles.css frontend/src/pages/Documents.test.tsx
git commit -m "Add admin document preview drawer"
```

---

### Task 4: Improve chat textarea keyboard behavior

**Files:**
- Modify: `frontend/src/pages/Chat.tsx`
- Modify: `frontend/src/pages/Chat.test.tsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Consumes: existing form `submit` handler and `sendChat`
- Produces: Enter-to-submit, Shift+Enter newline, composition-safe Enter, and no visible label

- [x] **Step 1: Write failing keyboard interaction tests**

Assert:

- the visible text `问题` is absent while `getByRole("textbox", { name: "问题" })` still works;
- typing a question and pressing Enter calls `sendChat` once;
- Shift+Enter adds a newline and does not call `sendChat`;
- a composition Enter event does not call `sendChat`.

Run:

```bash
pnpm --dir frontend test -- --run src/pages/Chat.test.tsx
```

Expected: FAIL because the visible label remains and Enter currently inserts a newline.

- [x] **Step 2: Implement keyboard behavior**

Remove the visible `<label>`, add `aria-label="问题"` to the textarea, and add `onKeyDown` logic that calls `event.currentTarget.form?.requestSubmit()` only when:

```typescript
event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing
```

Call `preventDefault()` only for the send path. Preserve the existing disabled and trimming behavior in `submit`.

- [x] **Step 3: Remove obsolete label styling and verify**

Remove `.composer label` rules that no longer apply. Run all frontend tests and production build:

```bash
pnpm --dir frontend test -- --run
pnpm --dir frontend build
```

Expected: all tests and build pass.

- [x] **Step 4: Commit the chat interaction**

```bash
git add frontend/src/pages/Chat.tsx frontend/src/pages/Chat.test.tsx frontend/src/styles.css
git commit -m "Improve chat keyboard controls"
```

---

### Task 5: Rebuild, reindex, and run end-to-end acceptance

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/plans/2026-07-11-document-preview-and-retrieval.md` (check completed steps)

**Interfaces:**
- Consumes: all completed backend and frontend changes
- Produces: verified Docker services, upgraded `local-hash-v2` chunks, working admin preview, and a cited Claude answer

- [x] **Step 1: Run complete automated verification**

```bash
backend/.venv/bin/pytest -q backend/tests
pnpm --dir frontend test -- --run
pnpm --dir frontend build
docker compose config --quiet
git diff --check
```

Expected: all backend and frontend tests pass, frontend builds, Compose validates, and no whitespace errors are reported.

- [x] **Step 2: Rebuild and start the stack**

```bash
docker compose up -d --build
docker compose ps
```

Expected: postgres and backend become healthy; frontend and ingest remain running.

- [x] **Step 3: Verify automatic reindexing**

Poll PostgreSQL until all three seeded documents are READY. Query chunk metadata and assert every chunk has:

```json
{"embedding_version": "local-hash-v2"}
```

Do not delete the existing Docker volume during this check.

- [x] **Step 4: Verify API permissions and preview data**

Log in as `andy.admin`, fetch the employee handbook detail, and assert permissions and ordered chunks are present. Log in as `alice.programmer` and assert the same admin detail endpoint returns `403`.

- [x] **Step 5: Verify the real knowledge question**

Through `/api/chat`, ask as `andy.admin`:

```text
公司的核心协作时间是什么？
```

Assert HTTP `200`, the answer contains `10:00` and `16:00`, and citations include `员工手册` / `工作时间`.

- [x] **Step 6: Update README and commit final delivery**

Add one short feature bullet for admin extracted-content preview and document that old local indexes upgrade automatically on worker start.

```bash
git add README.md docs/superpowers/plans/2026-07-11-document-preview-and-retrieval.md
git commit -m "Document preview and retrieval behavior"
git push origin main
```

Expected: `origin/main` matches local HEAD and the worktree is clean.
