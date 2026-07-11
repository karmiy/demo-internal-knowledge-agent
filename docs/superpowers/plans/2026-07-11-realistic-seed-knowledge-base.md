# Realistic Seed Knowledge Base Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the Demo from three tiny documents to twelve realistic, permissioned SaaS-company knowledge-base documents that an administrator can browse and preview.

**Architecture:** Keep the existing document model, admin UI, ACL, Ingest Worker, and local embedding pipeline. Make seed reconciliation source-path-based so changed seed files update in place and requeue for ingestion, then add twelve medium-length Markdown documents distributed across authenticated, Engineering, HR/Admin, and Admin-only scopes.

**Tech Stack:** Python, FastAPI, SQLAlchemy, PostgreSQL/pgvector, Markdown, Docker Compose

## Global Constraints

- Work directly on `main`, as requested by the user.
- Add data only; do not add salary, employee, or other business-management pages.
- Keep `employee-handbook.md`, `engineering-guide.md`, and `hr-compensation-policy.md` as stable filenames for existing-volume upgrades.
- Seed exactly 12 managed documents: Alice can access 9, Helen 8, and Andy all 12.
- Every document contains 4–6 substantive sections and only fictional Demo data.
- Preserve user-uploaded documents and the existing database volume.
- Changed seed content updates the existing Document in place, becomes PENDING, and is re-ingested with `local-hash-v2`.

---

### Task 1: Make seed documents update safely in place

**Files:**
- Modify: `backend/app/seed.py`
- Create: `backend/tests/test_seed.py`

**Interfaces:**
- Extends: `_seed_documents(session, admin, *, seed_root=None, target_root=None, document_specs=None) -> None`
- Consumes: seed tuples shaped as `(title, filename, permissions)`
- Produces: source-path-based create/update, exact permission synchronization, and PENDING requeue only when title or content changes

- [ ] **Step 1: Write failing reconciliation tests**

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
```

Run:

```bash
backend/.venv/bin/pytest -q backend/tests/test_seed.py
```

Expected: FAIL because `_seed_documents` currently finds by checksum and cannot inject temporary roots/specs.

- [ ] **Step 2: Add injectable seed roots and specs**

Change `_seed_documents` so production defaults remain `/seed-documents`, `get_settings().document_root`, and `DEMO_DOCUMENTS`, while tests can supply temporary paths and a one-document tuple.

The stable lookup must be:

```python
document = session.scalar(
    select(Document).where(Document.source_path == str(target))
)
```

Do not use checksum as the seed document identity.

- [ ] **Step 3: Implement in-place content/title updates**

For an existing document, compare the current title and checksum before assignment. When either changed:

```python
document.title = title
document.checksum = checksum
document.status = DocumentStatus.PENDING
document.error = None
```

Copy changed bytes to the stable target path. If neither changed, do not alter READY/PROCESSING/FAILED status or existing chunks.

- [ ] **Step 4: Synchronize permissions exactly**

Build the desired pair set. Delete existing `DocumentPermission` rows not in that set and add missing pairs. Do not modify matching rows.

- [ ] **Step 5: Run tests and commit**

```bash
backend/.venv/bin/pytest -q backend/tests/test_seed.py backend/tests/test_ingest.py backend/tests/test_ingestion_worker.py
backend/.venv/bin/pytest -q backend/tests
git add backend/app/seed.py backend/tests/test_seed.py
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

- [ ] **Step 1: Write failing catalog/content tests**

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

- [ ] **Step 2: Expand the three existing documents**

Write 4–6 factual sections for:

- `员工手册` while retaining the core collaboration time `10:00–16:00`;
- `工程研发规范` using stable file `engineering-guide.md`;
- `薪酬与职级制度` using stable file `hr-compensation-policy.md`, with annual review starting in March and no personal salaries.

- [ ] **Step 3: Write the six authenticated documents**

Complete the authenticated catalog with `考勤与休假制度`, `差旅与报销制度`, `信息安全规范`, `远程办公指南`, and `新员工入职指南`. Include ordinary leave requested at least 3 working days ahead and travel expense submission within 10 working days after return.

- [ ] **Step 4: Write the remaining restricted documents**

Add:

- Engineering: `发布与变更管理`, `故障响应与值班手册`, including code-owner approval, health verification, P1 response within 10 minutes, and updates every 30 minutes;
- HR/Admin: `绩效评估制度`;
- Admin: `采购与供应商管理制度`, including three quotes for purchases at or above `50,000 CNY`.

- [ ] **Step 5: Register exact ACL scopes**

Update `DEMO_DOCUMENTS` so:

- authenticated documents use `(SubjectType.AUTHENTICATED, "*")`;
- Engineering documents use `(SubjectType.DEPARTMENT, "engineering")`;
- HR documents use role pairs `hr` and `admin`;
- procurement uses `(SubjectType.ROLE, "admin")`.

- [ ] **Step 6: Run tests and commit**

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

- [ ] **Step 1: Update README**

State that the Demo seeds 12 realistic documents and summarize the 6/3/2/1 ACL distribution. Add the six suggested questions from the design and keep the existing account/password section.

- [ ] **Step 2: Run complete automated verification**

```bash
backend/.venv/bin/pytest -q backend/tests
pnpm --dir frontend test -- --run
pnpm --dir frontend build
docker compose config --quiet
git diff --check
```

Expected: all backend/frontend tests pass, production build succeeds, and Compose/whitespace checks are clean.

- [ ] **Step 3: Rebuild without deleting the existing volume**

```bash
docker compose up -d --build
docker compose ps
```

Do not execute `docker compose down -v`. Poll until all 12 seed-managed source paths are READY.

- [ ] **Step 4: Verify database identity and index state**

Query PostgreSQL and assert:

- exactly 12 configured source paths exist once each;
- the three legacy IDs still exist under their stable source paths;
- all 12 are READY;
- every chunk has `embedding_version = local-hash-v2`.

- [ ] **Step 5: Verify admin frontend/API visibility and ACL counts**

Log in as `andy.admin`; assert the admin list returns 12 seed documents and a newly added document detail returns 4–6 ordered chunks. Verify database ACL predicates make 9 documents accessible to Alice, 8 to Helen, and 12 to Andy. User-uploaded documents, if any, must remain untouched and are excluded from these seed counts.

- [ ] **Step 6: Run four real knowledge questions**

Use the appropriate identities and assert answer facts plus citations:

```text
Alice: 年假申请需要提前多久？ -> 3 个工作日 / 考勤与休假制度
Alice: P1 故障需要多快响应？ -> 10 分钟 / 故障响应与值班手册
Helen: 薪酬复核通常在什么时候进行？ -> 3 月 / 薪酬与职级制度
Andy: 采购达到什么条件需要多家比价？ -> 50,000 CNY、3 家 / 采购与供应商管理制度
```

- [ ] **Step 7: Commit and push delivery**

```bash
git add README.md docs/superpowers/specs/2026-07-11-realistic-seed-knowledge-base-design.md docs/superpowers/plans/2026-07-11-realistic-seed-knowledge-base.md
git commit -m "Document expanded demo knowledge base"
git push origin main
```

Expected: local HEAD equals `origin/main`, worktree is clean, and the stack remains running.
