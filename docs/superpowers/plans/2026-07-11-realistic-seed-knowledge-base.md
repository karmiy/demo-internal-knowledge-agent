# Realistic Seed Knowledge Base Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the Demo from three tiny documents to twelve realistic, permissioned SaaS-company knowledge-base documents that an administrator can browse and preview.

**Architecture:** Keep the existing admin UI, ACL, Ingest Worker, and local embedding pipeline. Extend document ownership metadata only as required to distinguish managed seeds from uploads, and make seed reconciliation source-path-based, process-serialized, token-owned, and crash-recoverable so changed seed files update in place before requeueing for ingestion. Then add twelve medium-length Markdown documents distributed across authenticated, Engineering, HR/Admin, and Admin-only scopes.

**Tech Stack:** Python, FastAPI, SQLAlchemy, PostgreSQL/pgvector, Markdown, Docker Compose

## Global Constraints

- Work directly on `main`, as requested by the user.
- Add data only; do not add salary, employee, or other business-management pages.
- Keep `employee-handbook.md`, `engineering-guide.md`, and `hr-compensation-policy.md` as stable filenames for existing-volume upgrades.
- Seed exactly 12 managed documents: Alice can access 9, Helen 8, and Andy all 12.
- Every document contains 4–6 substantive sections and only fictional Demo data.
- Preserve user-uploaded documents and the existing database volume.
- Changed seed content updates the existing Document in place, becomes PENDING only after the stable target file is installed, and is re-ingested with `local-hash-v2`.
- Seed reconciliation assumes the Demo's Docker/Linux/macOS shared local document volume. Its `fcntl.flock` process lock is not a distributed-lock design for multi-host or arbitrary network-filesystem deployments.

---

### Task 1: Make seed documents update safely in place

**Files:**
- Modify: `backend/app/seed.py`
- Modify: `backend/app/models.py`
- Modify: `backend/app/retrieval/ingest.py`
- Modify: `backend/app/ingestion/worker.py`
- Modify: `backend/app/api/documents.py`
- Modify: `backend/alembic/versions/0002_allow_duplicate_document_checksums.py`
- Create: `backend/tests/test_seed.py`
- Create: `backend/tests/test_migrations.py`
- Modify: `backend/tests/test_documents_api.py`
- Modify: `backend/tests/test_ingest.py`
- Modify: `backend/tests/test_ingestion_worker.py`

**Interfaces:**
- Prepares inside the caller's transaction: `_prepare_seed_documents(session, admin, *, seed_root=None, target_root=None, document_specs=None) -> SeedPreparation`
  - Performs source-path row locking, metadata/permission reconciliation, tokenized staging-state assignment, and sibling temporary-file creation.
  - Does not commit, roll back, install target files, or expose PENDING state.
- Orchestrates the complete protocol using a session factory and admin ID: concrete signature `reconcile_seed_documents(admin_id, *, session_factory=SessionLocal, seed_root=None, target_root=None, document_specs=None, reconciliation_lock_timeout=5.0) -> None`
  - Owns the cross-process reconciliation lock, preparation transaction, row-locked file-install/finalization transaction, commits, rollbacks, and staging cleanup.
  - Publishes PENDING only after exact operation-token verification and atomic target installation.
- Consumes: seed tuples shaped as `(title, filename, permissions)`
- Produces: source-path-based create/update, exact permission synchronization, crash-recoverable tokenized staging, and safe PENDING requeue when title/content changes or an interrupted seed operation is recovered

- [x] **Step 1: Write failing reconciliation tests**

Use a real in-memory SQLAlchemy session and temporary source/target directories. Cover these behaviors:

```python
def test_changed_seed_updates_same_document_and_requeues(...):
    # First seed creates one document. Mark it READY, change source bytes,
    # seed again, then assert the same id remains, count is 1, checksum changes,
    # target bytes change, status is PENDING, and error is cleared.

def test_unchanged_seed_keeps_ready_document(...):
    # Seed the same bytes twice and assert the existing READY status remains.

def test_seed_synchronizes_permissions_exactly(...):
    # Change desired subjects from authenticated to role/hr + role/admin;
    # assert obsolete permission is deleted and only the two desired pairs remain.

def test_live_reconciler_lock_blocks_second_protocol(...):
    # Hold the stable target-root flock and assert another reconciler cannot
    # prepare or finalize database/file state.

def test_wrong_staging_token_cannot_finalize_or_replace(...):
    # Change the committed marker token and assert finalization rejects it
    # before replacing the target or publishing PENDING.
```

Run:

```bash
backend/.venv/bin/pytest -q backend/tests/test_seed.py
```

Expected: FAIL on the baseline because seed identity is checksum-based, roots/specs are fixed, and no transaction-participating preparation or lock-owning orchestration interface exists.

- [x] **Step 2: Add transaction-participating preparation**

Implement `_prepare_seed_documents` so production defaults remain `/seed-documents`, `get_settings().document_root`, and `DEMO_DOCUMENTS`, while tests can supply temporary paths and a one-document tuple. Return an explicit `SeedPreparation` containing per-document operation IDs, unique tokens, optional sibling staged paths, and stable targets. The helper participates in its caller's transaction and must not commit, roll back, or install targets.

The stable lookup must be:

```python
document = session.scalar(
    select(Document)
    .where(Document.source_path == str(target))
    .with_for_update()
)
```

Do not use checksum as the seed document identity.

- [x] **Step 3: Implement serialized two-transaction orchestration**

Implement `reconcile_seed_documents` as the only production owner of the complete document protocol:

- Acquire the stable target-root `fcntl.flock` with bounded wait and hold it through final commit.
- In the preparation transaction, mark each changed/recovery row `PROCESSING` with `seed_file_staging:<unique-token>` and commit while the old target remains installed.
- In the finalization transaction, lock every operation row, verify its exact token before any replacement, atomically `os.replace` sibling staged files while row locks are held, set the owned rows to `PENDING`/`error=None`, and commit.
- On replacement or final-commit failure, roll back to the committed unclaimable marker. The next exclusively locked run takes over abandoned tokens and recovers old or already-installed target bytes.
- If an ordinary worker owns a changed `PROCESSING` document, raise `SeedDocumentBusy`; production seeding retries this condition a bounded number of times.

If neither title, source checksum, nor target bytes changed, do not alter READY/PROCESSING/FAILED status or existing chunks.

- [x] **Step 4: Synchronize permissions exactly**

Inside preparation, build the desired pair set. Delete existing `DocumentPermission` rows not in that set and add missing pairs. Do not modify matching rows.

- [x] **Step 5: Preserve worker and upload concurrency safety**

- Ingestion and failure finalization must lock document rows and leave tokenized seed-staging markers untouched.
- Add `Document.is_seed`; allow honest seed/upload checksum equality while enforcing upload/upload uniqueness with the partial `uq_documents_upload_checksum` index.
- Keep the upload application pre-check, map only that PostgreSQL constraint or SQLite checksum-unique message to HTTP 409, and re-raise unrelated integrity errors after rollback/file cleanup.
- Downgrade must preflight duplicate checksums and fail with an actionable message before attempting the older global-unique index.

- [x] **Step 6: Run tests and commit**

```bash
backend/.venv/bin/pytest -q backend/tests/test_seed.py backend/tests/test_migrations.py backend/tests/test_documents_api.py backend/tests/test_ingest.py backend/tests/test_ingestion_worker.py
backend/.venv/bin/pytest -q backend/tests
git add backend/app backend/alembic/versions backend/tests
git commit -m "Support in-place seed document updates"
```

Expected: focused tests and complete backend suite pass.

---

### Task 2: Add twelve realistic knowledge-base documents

**Files:**
- Modify: `backend/app/seed.py`
- Modify: `documents/employee-handbook.md`
- Modify: `documents/engineering-guide.md`
- Modify: `documents/hr-compensation-policy.md`
- Create: `documents/attendance-leave-policy.md`
- Create: `documents/travel-expense-policy.md`
- Create: `documents/information-security-policy.md`
- Create: `documents/remote-work-guide.md`
- Create: `documents/onboarding-guide.md`
- Create: `documents/release-change-management.md`
- Create: `documents/incident-response-oncall.md`
- Create: `documents/performance-review-policy.md`
- Create: `documents/procurement-vendor-policy.md`
- Modify: `backend/tests/test_seed.py`

**Interfaces:**
- Produces: `DEMO_DOCUMENTS` with exactly 12 `(title, filename, permissions)` entries
- Consumes: existing Markdown parser and `local-hash-v2` ingestion
- Produces: 6 authenticated, 3 Engineering, 2 HR/Admin, and 1 Admin-only documents

- [x] **Step 1: Write failing catalog/content tests**

Add assertions that:

```python
assert len(DEMO_DOCUMENTS) == 12
assert permission_counts == {
    "authenticated": 6,
    "engineering": 3,
    "hr_admin": 2,
    "admin": 1,
}
```

For every configured file, assert it exists, parses into 4–6 non-empty sections, and has no duplicate filename. Assert the corpus contains the exact acceptance facts `10:00`, `16:00`, `3 个工作日`, `10 个工作日`, `10 分钟`, `30 分钟`, `3 月`, `50,000 CNY`, and `3 家供应商`.

Run the catalog tests and expect FAIL because only three files/specs exist.

- [x] **Step 2: Expand the three existing documents**

Write 4–6 factual sections for:

- `员工手册` while retaining the core collaboration time `10:00–16:00`;
- `工程研发规范` using stable file `engineering-guide.md`;
- `薪酬与职级制度` using stable file `hr-compensation-policy.md`, with annual review starting in March and no personal salaries.

- [x] **Step 3: Write the six authenticated documents**

Complete the authenticated catalog with `考勤与休假制度`, `差旅与报销制度`, `信息安全规范`, `远程办公指南`, and `新员工入职指南`. Include ordinary leave requested at least 3 working days ahead and travel expense submission within 10 working days after return.

- [x] **Step 4: Write the remaining restricted documents**

Add:

- Engineering: `发布与变更管理`, `故障响应与值班手册`, including code-owner approval, health verification, P1 response within 10 minutes, and updates every 30 minutes;
- HR/Admin: `绩效评估制度`;
- Admin: `采购与供应商管理制度`, including three quotes for purchases at or above `50,000 CNY`.

- [x] **Step 5: Register exact ACL scopes**

Update `DEMO_DOCUMENTS` so:

- authenticated documents use `(SubjectType.AUTHENTICATED, "*")`;
- Engineering documents use `(SubjectType.DEPARTMENT, "engineering")`;
- HR documents use role pairs `hr` and `admin`;
- procurement uses `(SubjectType.ROLE, "admin")`.

- [x] **Step 6: Run tests and commit**

```bash
backend/.venv/bin/pytest -q backend/tests/test_seed.py backend/tests/test_ingest.py backend/tests/test_embeddings.py
backend/.venv/bin/pytest -q backend/tests
git add backend/app/seed.py backend/tests/test_seed.py documents
git commit -m "Add realistic SaaS knowledge base data"
```

Expected: catalog/content tests and complete backend suite pass.

---

### Task 3: Document and accept the expanded corpus

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/plans/2026-07-11-realistic-seed-knowledge-base.md` (check completed steps)

**Interfaces:**
- Consumes: all Task 1–2 data and seed behavior
- Produces: a running retained-volume stack with 12 READY managed documents and user-facing test guidance

- [x] **Step 1: Update README**

State that the Demo seeds 12 realistic documents and summarize the 6/3/2/1 ACL distribution. Add the six suggested questions from the design and keep the existing account/password section.

- [x] **Step 2: Run complete automated verification**

```bash
backend/.venv/bin/pytest -q backend/tests
pnpm --dir frontend test -- --run
pnpm --dir frontend build
docker compose config --quiet
git diff --check
```

Expected: all backend/frontend tests pass, production build succeeds, and Compose/whitespace checks are clean.

- [x] **Step 3: Rebuild without deleting the existing volume**

```bash
docker compose up -d --build
docker compose ps
```

Do not execute `docker compose down -v`. Poll until all 12 seed-managed source paths are READY.

- [x] **Step 4: Verify database identity and index state**

Query PostgreSQL and assert:

- exactly 12 configured source paths exist once each;
- the three legacy IDs still exist under their stable source paths;
- all 12 are READY;
- every chunk has `embedding_version = local-hash-v2`.

- [x] **Step 5: Verify admin frontend/API visibility and ACL counts**

Log in as `andy.admin`; assert the admin list returns 12 seed documents and a newly added document detail returns 4–6 ordered chunks. Verify database ACL predicates make 9 documents accessible to Alice, 8 to Helen, and 12 to Andy. User-uploaded documents, if any, must remain untouched and are excluded from these seed counts.

- [x] **Step 6: Run four real knowledge questions**

Use the appropriate identities and assert answer facts plus citations:

```text
Alice: 年假申请需要提前多久？ -> 3 个工作日 / 考勤与休假制度
Alice: P1 故障需要多快响应？ -> 10 分钟 / 故障响应与值班手册
Helen: 薪酬复核通常在什么时候进行？ -> 3 月 / 薪酬与职级制度
Andy: 采购达到什么条件需要多家比价？ -> 50,000 CNY、3 家 / 采购与供应商管理制度
```

- [x] **Step 7: Commit and push delivery**

```bash
git add README.md docs/superpowers/specs/2026-07-11-realistic-seed-knowledge-base-design.md docs/superpowers/plans/2026-07-11-realistic-seed-knowledge-base.md
git commit -m "Document expanded demo knowledge base"
git push origin main
```

Expected: local HEAD equals `origin/main`, worktree is clean, and the stack remains running.
