# Vector Storage Note Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Explain where Embedding vectors are stored on the design page.

**Architecture:** Add a static explanatory callout above the schema grid and visually emphasize the existing `document_chunks` card. Reuse the page's existing HTML/CSS and design tokens.

**Tech Stack:** Static HTML and CSS

## Global Constraints

- Modify only documentation.
- Add no dependency.
- Keep desktop and mobile layouts free of horizontal overflow.

---

### Task 1: Add vector-storage explanation

**Files:**
- Modify: `docs/design.html`

**Interfaces:**
- Consumes: Existing `#data` section and `.schema` entity grid.
- Produces: A visible vector-storage callout and highlighted `document_chunks` entity.

- [x] **Step 1: Add the callout HTML and exact storage explanation.**
- [x] **Step 2: Add scoped callout and entity-highlight styles.**
- [x] **Step 3: Verify HTML parsing, required copy, and responsive geometry.**
- [x] **Step 4: Commit the documentation change.**
