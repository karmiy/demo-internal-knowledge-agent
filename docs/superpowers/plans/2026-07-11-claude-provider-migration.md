# Claude Provider Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all OpenAI runtime usage with Claude answer generation and deterministic local document embeddings.

**Architecture:** A focused `LocalHashEmbeddings` service implements LangChain's embedding interface and is shared by ingest and retrieval. `ChatAnthropic` is the only remote model client; FastAPI continues to inject trusted users into the existing LangGraph workflow, and all database, ACL, citation, and frontend contracts stay stable.

**Tech Stack:** Python 3.12, LangChain 1.x, `langchain-anthropic`, Claude Sonnet 4.6, LangGraph 1.x, PostgreSQL 16 + pgvector, pytest, Docker Compose.

## Global Constraints

- Remove `langchain-openai`, `OPENAI_API_KEY`, `OpenAIEmbeddings`, and `ChatOpenAI` from runtime code and documentation.
- Use the pinned Claude API model ID `claude-sonnet-4-6`; Anthropic documents 4.6-generation dateless IDs as fixed snapshots: https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions
- Instantiate Claude through the dedicated `ChatAnthropic` integration following LangChain's official guide: https://docs.langchain.com/oss/python/integrations/chat/anthropic
- Keep `EMBEDDING_DIMENSIONS=1536`; no database migration or vector data conversion is required.
- Ingest must run without an Anthropic key or any model download.
- Never commit, print, or pass a real API key in a shell command; the operator supplies it through the ignored `.env` file.
- Work directly on `main`, with a focused commit after each task.

---

## Target File Map

```text
backend/app/embeddings.py                 # deterministic local embedding implementation and factory
backend/tests/test_embeddings.py          # dimensions, determinism, normalization, similarity
backend/app/config.py                     # Anthropic secret and Claude model settings
backend/app/api/chat.py                   # ChatAnthropic runtime and response text extraction
backend/app/ingestion/worker.py            # local embedder factory use
backend/tests/test_claude_runtime.py       # missing-key and content-block behavior
backend/pyproject.toml                     # provider dependency replacement
backend/uv.lock                            # resolved dependency graph
.env.example                               # Anthropic-only runtime configuration
README.md                                  # Claude setup and local embedding limitation
```

### Task 1: Deterministic local embeddings

**Files:**
- Create: `backend/app/embeddings.py`
- Create: `backend/tests/test_embeddings.py`

**Interfaces:**
- Produces: `LocalHashEmbeddings(dimensions: int)` implementing `embed_documents(list[str]) -> list[list[float]]` and `embed_query(str) -> list[float]`.
- Produces: `build_local_embedder() -> LocalHashEmbeddings` using `get_settings().embedding_dimensions`.
- Consumes: standard-library `hashlib`, `math`, `re`, and `unicodedata`; `langchain_core.embeddings.Embeddings`.

- [ ] **Step 1: Write failing embedding behavior tests**

```python
from math import sqrt

import pytest

from app.embeddings import LocalHashEmbeddings


def dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def test_embedding_is_deterministic_normalized_and_configured() -> None:
    embedder = LocalHashEmbeddings(dimensions=64)
    first = embedder.embed_query("工程发布流程")
    second = embedder.embed_query("工程发布流程")
    assert first == second
    assert len(first) == 64
    assert sqrt(dot(first, first)) == pytest.approx(1.0)


def test_shared_chinese_terms_rank_above_unrelated_text() -> None:
    embedder = LocalHashEmbeddings(dimensions=256)
    query = embedder.embed_query("工程发布流程")
    related = embedder.embed_query("工程团队发布检查流程")
    unrelated = embedder.embed_query("年度休假与报销制度")
    assert dot(query, related) > dot(query, unrelated)
```

- [ ] **Step 2: Run the focused tests and confirm the missing module failure**

Run: `cd backend && .venv/bin/python -m pytest tests/test_embeddings.py -q`

Expected: collection fails with `ModuleNotFoundError: No module named 'app.embeddings'`.

- [ ] **Step 3: Implement the minimal local embedder**

```python
class LocalHashEmbeddings(Embeddings):
    def __init__(self, dimensions: int) -> None:
        if dimensions < 32:
            raise ValueError("dimensions must be at least 32")
        self.dimensions = dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)
```

Normalize text with NFKC and lowercase. Extract Latin alphanumeric words plus Chinese unigrams and adjacent bigrams. For every feature, use `hashlib.blake2b(feature.encode(), digest_size=16).digest()`; the first eight bytes select the dimension and the ninth byte selects a positive or negative sign. L2-normalize non-empty vectors and return an all-zero vector for empty text.

- [ ] **Step 4: Run focused and full backend tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_embeddings.py -q && .venv/bin/python -m pytest -q`

Expected: embedding tests pass and the existing 36 backend tests remain green.

- [ ] **Step 5: Commit the local embedding service**

```bash
git add backend/app/embeddings.py backend/tests/test_embeddings.py
git commit -m "Add deterministic local document embeddings"
git push origin main
```

### Task 2: Claude runtime and provider dependency

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/api/chat.py`
- Modify: `backend/app/ingestion/worker.py`
- Modify: `backend/pyproject.toml`
- Modify: `backend/uv.lock`
- Create: `backend/tests/test_claude_runtime.py`

**Interfaces:**
- Consumes: `build_local_embedder()` from Task 1.
- Produces: settings `anthropic_api_key: SecretStr | None`, `chat_model: str = "claude-sonnet-4-6"`, and `chat_max_tokens: int = 2048`.
- Produces: `_message_text(content: str | list[object]) -> str` for safe LangChain Anthropic content conversion.
- Preserves: `get_agent_runner()` and HTTP response schemas.

- [ ] **Step 1: Write failing Claude runtime tests**

```python
import pytest

from app.api.chat import RuntimeServices, _message_text
from app.config import Settings


def test_runtime_requires_anthropic_key(monkeypatch) -> None:
    settings = Settings(anthropic_api_key=None)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        RuntimeServices(settings=settings)


def test_message_text_extracts_anthropic_text_blocks() -> None:
    content = [
        {"type": "text", "text": "第一段"},
        {"type": "tool_use", "name": "ignored"},
        {"type": "text", "text": "第二段"},
    ]
    assert _message_text(content) == "第一段\n第二段"
```

- [ ] **Step 2: Run tests and verify they fail because Claude runtime is absent**

Run: `cd backend && .venv/bin/python -m pytest tests/test_claude_runtime.py -q`

Expected: import or signature failure referencing missing Anthropic behavior.

- [ ] **Step 3: Replace provider configuration and dependencies**

In `pyproject.toml`, replace:

```toml
"langchain-openai>=1,<2",
```

with:

```toml
"langchain-anthropic>=1,<2",
```

In settings, remove `openai_api_key` and `embedding_model`, then add the Anthropic secret and `chat_max_tokens` fields defined above.

```python
anthropic_api_key: SecretStr | None = None
chat_model: str = "claude-sonnet-4-6"
chat_max_tokens: int = 2048
embedding_dimensions: int = 1536
```

- [ ] **Step 4: Implement `ChatAnthropic` runtime and local retrieval embedding**

```python
self.embedder = build_local_embedder()
self.model = ChatAnthropic(
    model=settings.chat_model,
    api_key=api_key,
    temperature=0,
    max_tokens=settings.chat_max_tokens,
)
```

Accept an optional `Settings` instance in `RuntimeServices.__init__` for focused testing. `_message_text` returns string content unchanged; for list content, it joins only dictionaries whose `type` is `text` and whose `text` value is a string. `compose` uses this helper rather than `str(response.content)`.

Change the ingestion worker's `build_embedder()` to return `build_local_embedder()` with no API-key access.

- [ ] **Step 5: Regenerate the Python lock and run tests**

Run: `cd backend && uv lock && uv sync --extra dev && .venv/bin/python -m pytest -q`

Expected: dependency resolution succeeds, no `langchain-openai` direct dependency remains, and all backend tests pass.

- [ ] **Step 6: Verify the OpenAI runtime is gone**

Run: `rg -n "OpenAI|OPENAI|openai" backend/app backend/pyproject.toml .env.example README.md`

Expected: no runtime or configuration matches; historical design documents are outside this check.

- [ ] **Step 7: Commit the Claude runtime**

```bash
git add backend/app/config.py backend/app/api/chat.py backend/app/ingestion/worker.py backend/pyproject.toml backend/uv.lock backend/tests/test_claude_runtime.py
git commit -m "Switch agent runtime to Claude"
git push origin main
```

### Task 3: Configuration, documentation, and container acceptance

**Files:**
- Modify: `.env.example`
- Modify: `README.md`

**Interfaces:**
- Consumes: Claude runtime and local embedder from Tasks 1 and 2.
- Produces: documented operator setup using `ANTHROPIC_API_KEY` and `CHAT_MODEL=claude-sonnet-4-6`.

- [ ] **Step 1: Update safe configuration examples**

Use this provider section in `.env.example`:

```dotenv
ANTHROPIC_API_KEY=
CHAT_MODEL=claude-sonnet-4-6
CHAT_MAX_TOKENS=2048
EMBEDDING_DIMENSIONS=1536
```

Do not add a real key.

- [ ] **Step 2: Update README setup and architecture language**

State that Claude generates answers, local hashing creates pgvector embeddings, ingest requires no remote model, and local embeddings are lexical Demo infrastructure rather than a production semantic model. Keep the existing demo users, ACL explanation, and Compose commands.

- [ ] **Step 3: Run final source and test checks**

Run:

```bash
rg -n "OpenAI|OPENAI|openai" backend/app backend/pyproject.toml .env.example README.md
cd backend && .venv/bin/python -m pytest -q
cd ../frontend && pnpm test -- --run && pnpm run build
cd .. && docker compose config --quiet && git diff --check
```

Expected: no OpenAI matches, all backend/frontend tests pass, frontend production build succeeds, and Compose configuration is valid.

- [ ] **Step 4: Rebuild and start all services without an embedding API key**

Run:

```bash
docker compose build backend frontend
docker compose up -d postgres backend ingest frontend
docker compose ps
```

Expected: all four services are running; PostgreSQL and backend are healthy. Ingest processes seed documents with local embeddings even when `ANTHROPIC_API_KEY` is empty.

- [ ] **Step 5: Verify local ingest and ACL retrieval**

Run:

```bash
docker compose exec -T postgres psql -U knowledge -d knowledge -c \
  "select d.title, d.status, count(c.id) chunks from documents d left join document_chunks c on c.document_id=d.id group by d.id order by d.title;"
docker compose exec -T backend python -c \
  'from app.db import SessionLocal; from app.embeddings import build_local_embedder; from app.models import User; from app.retrieval.search import search_documents; from sqlalchemy import select; s=SessionLocal(); u=s.scalar(select(User).where(User.username=="alice.programmer")); titles=sorted(set(x.document_title for x in search_documents("工程发布流程", u, s, build_local_embedder(), limit=10))); print(titles); assert "HR 薪酬制度" not in titles; s.close()'
```

Expected: all three documents are `READY` with at least one chunk; Alice's titles exclude `HR 薪酬制度`.

- [ ] **Step 6: Verify Claude chat after the operator supplies the ignored local secret**

The operator adds `ANTHROPIC_API_KEY` directly to `.env`, outside Git and command logs. Recreate backend with `docker compose up -d --force-recreate backend`, log in as `alice.programmer`, and send `POST /api/chat` with `{"message":"工程发布流程是什么？"}`. Expected: HTTP 200 with a non-empty answer, at least one citation, and `searched_documents` activity.

- [ ] **Step 7: Commit final provider documentation**

```bash
git add .env.example README.md
git commit -m "Document Claude-only demo setup"
git push origin main
```
