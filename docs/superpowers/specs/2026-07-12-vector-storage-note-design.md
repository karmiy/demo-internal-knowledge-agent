# Vector Storage Note Design

## Goal

Make it immediately clear that Chunk text and its Embedding vector are stored together in the PostgreSQL `document_chunks` table, with pgvector providing the vector column type and similarity operations.

## Placement and presentation

- Add one explanatory callout between the Data section heading and the entity grid.
- Show `document_chunks.content` and `document_chunks.embedding vector(n)` as two fields in the same table.
- Highlight the existing `document_chunks` entity card without changing the other schema cards.
- Preserve the current editorial visual style and responsive layout.

## Scope

Only `docs/design.html` changes. No runtime code, database schema, dependency, or service changes.
