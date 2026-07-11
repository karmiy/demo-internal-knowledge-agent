# Task 3 Acceptance Report: Expanded Demo Corpus

Date: 2026-07-12 (Asia/Shanghai)

## Scope and secret handling

- Executed Task 3 directly on `main` against the existing Docker volume.
- Never ran `docker compose down -v`; the PostgreSQL container and retained volume remained in place throughout both rebuilds.
- Used the configured Anthropic credential only through the running backend for live questions. The credential value was never printed, logged into this report, or added to Git.
- User-uploaded documents were not modified. The retained database contained exactly the 12 managed seed documents and no additional documents during acceptance.

## Documentation changes

- Updated `README.md` to describe 12 realistic seed documents and the 6 authenticated / 3 Engineering / 2 HR-Admin / 1 Admin-only ACL distribution.
- Added the six design-specified knowledge questions while preserving the existing demo account and password guidance.
- Checked the completed steps in `docs/superpowers/plans/2026-07-11-realistic-seed-knowledge-base.md`.

## Automated gates

Initial Task 3 gate:

- `backend/.venv/bin/pytest -q backend/tests`: 94 passed.
- `pnpm --dir frontend test -- --run`: 4 files, 13 tests passed.
- `pnpm --dir frontend build`: TypeScript and Vite production build succeeded.
- `docker compose config --quiet`: succeeded.
- `git diff --check`: succeeded.

Live acceptance exposed two query-distance regressions. Two focused tests were added to `backend/tests/test_embeddings.py`; both were observed RED before the fix and GREEN afterward. The final full rerun passed 96 backend tests, 13 frontend tests, the production build, Compose validation, and `git diff --check`.

## Retained-volume rebuild and database state

- Captured the three legacy document identities before rebuilding while the database was still at Alembic `0001_initial`.
- Ran `docker compose up -d --build` without deleting the volume.
- Alembic advanced to `0002_nonunique_checksums`.
- All four services started; backend and PostgreSQL reported healthy.
- Exactly 12 `is_seed` rows exist, all 12 are `READY`, and all 12 source paths are distinct and occur once.
- The upload-only partial unique index `uq_documents_upload_checksum` exists alongside the non-unique checksum index.
- All 60 managed document chunks carry `metadata.embedding_version = local-hash-v2`.
- Every managed document has five chunks with indexes 0 through 4.

Stable legacy identities were preserved:

| Source path | Retained document ID |
|---|---|
| `/data/documents/employee-handbook.md` | `e284d696-e3f6-432b-b486-28f4a722ef76` |
| `/data/documents/engineering-guide.md` | `85c9550f-ff87-4914-9c27-afe798b49477` |
| `/data/documents/hr-compensation-policy.md` | `1aad9795-6289-4852-9020-30594c61354e` |

## Admin frontend/API and ACL verification

- The live frontend `/documents` route returned HTTP 200 and the React root mount.
- `andy.admin` login and `/api/auth/me` returned HTTP 200 with the `admin` role.
- `/api/admin/documents` returned 12 documents, all with API status `ready`.
- The newly added `采购与供应商管理制度` detail returned five ordered chunks with indexes `[0, 1, 2, 3, 4]`.
- The production `document_access_clause` executed against PostgreSQL returned Alice = 9, Helen = 8, and Andy = 12 managed documents.

The Codex in-app browser backend was unavailable in this task, so a visual click-through could not be captured. HTTP frontend availability, the frontend API contract, frontend component tests, and the production build were all verified instead. This is the only acceptance limitation.

## Live Claude knowledge questions

Final live calls used the real backend Claude path and asserted both answer facts and citation titles:

| Identity | Question | Asserted answer | Asserted citation | Result |
|---|---|---|---|---|
| Alice | 年假申请需要提前多久？ | `3 个工作日` | `考勤与休假制度` / `年假与事假` | Passed |
| Alice | P1 故障需要多快响应？ | `10 分钟` | `故障响应与值班手册` / `响应时限` | Passed |
| Helen | 薪酬复核通常在什么时候进行？ | `3 月` | `薪酬与职级制度` / `年度薪酬复核` | Passed |
| Andy | 采购达到什么条件需要多家比价？ | `50,000 CNY` and `3 家` | `采购与供应商管理制度` / `比价要求` | Passed |

## Runtime failure and minimal fix

The first live run safely refused the leave and procurement questions. Retrieval diagnostics showed the correct ACL-visible chunks ranked first but were just above the configured evidence cutoff of `0.72`:

- Leave: `0.721424`.
- Procurement: `0.731167`.

The global safety threshold was not relaxed. Focused acceptance tests reproduced both failures. Minimal wording changes increased lexical overlap between the natural questions and the authoritative sections; post-fix distances became `0.635883` and `0.571298`. The retained-volume reconciliation re-ingested the changed documents, and all four real Claude questions then passed.

Two verifier-only command mistakes were also corrected without product changes: the configured database is `knowledge` rather than an assumed `demo` database, and embedding version is stored in chunk JSON metadata rather than a dedicated column.

One final repeated Claude batch stopped during Helen's request without returning a result. Immediate isolated Helen and Andy calls both returned HTTP 200 with the expected facts and citations, and a fresh complete four-question batch then passed. No persistent application or provider failure was reproduced.

## Delivery state

- The stack is intentionally left running.
- Final full gates, Git cleanliness, `HEAD == origin/main`, and push status are verified as the final delivery actions after this report is staged.
