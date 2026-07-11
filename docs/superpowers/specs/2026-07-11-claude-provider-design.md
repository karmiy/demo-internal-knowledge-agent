# Claude Provider Migration Design

## Objective

Remove the OpenAI runtime dependency from the internal knowledge Agent Demo. Claude generates answers, while a deterministic local embedding implementation supplies document and query vectors without another API provider or model download.

## Architecture

- `ChatAnthropic` replaces `ChatOpenAI` in the chat runtime.
- `LocalHashEmbeddings` implements the LangChain embedding interface with `embed_documents` and `embed_query`.
- The local embedder tokenizes normalized Latin words and overlapping Chinese character n-grams, hashes features into the configured vector dimensions, and L2-normalizes the result.
- Ingest and retrieval share the same embedder factory so stored and query vectors always use identical logic.
- PostgreSQL, pgvector dimensions, ACL filtering, LangGraph routing, citations, salary policy, and the React API contract remain unchanged.

## Configuration

- Add `ANTHROPIC_API_KEY` as an optional secret-backed setting.
- Set the default chat model to a currently supported Claude model after verifying Anthropic's official model documentation during implementation.
- Remove `OPENAI_API_KEY` and `EMBEDDING_MODEL` from application settings and `.env.example`.
- Keep `EMBEDDING_DIMENSIONS=1536` so the existing pgvector schema does not require a destructive migration.
- Never commit, print, or place a real Anthropic key in tool commands. The operator adds it directly to the ignored local `.env` file.

## Dependency Changes

- Replace `langchain-openai` with `langchain-anthropic`.
- Regenerate `uv.lock` and rebuild the backend image.
- No local ML framework or downloadable embedding model is added.

## Error Handling

- Ingest works without an Anthropic key because local embeddings need no network access.
- Chat returns the existing sanitized HTTP 503 response when `ANTHROPIC_API_KEY` is absent.
- Claude API errors remain generic at the HTTP boundary and must not expose secrets or provider payloads.

## Tests and Acceptance

- Test local embeddings for determinism, configured dimensions, normalization, and shared-term similarity.
- Test runtime construction fails safely without an Anthropic key.
- Run all backend and frontend tests.
- Regenerate the lock file, build both Docker images, start all four services, and verify seed documents reach `ready` without an external embedding call.
- With a locally supplied Anthropic key, verify an authenticated chat request reaches Claude and returns the established response contract.

## Limitations

Local hashing embeddings provide lexical similarity rather than high-quality semantic similarity. This is appropriate for a lightweight, dependency-free Demo but should be replaced by an approved enterprise embedding model for production.
