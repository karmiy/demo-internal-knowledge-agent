# Unified Agent Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the design page's separated architecture panels into one connected end-to-end question flow.

**Architecture:** Keep the diagram dependency-free in `docs/design.html`. Use semantic HTML and CSS grids/pseudo-element connectors to show the main execution path, route branches, nested calls, merge, answer composition, verification, audit, and response.

**Tech Stack:** Static HTML, CSS, existing design-page JavaScript

## Global Constraints

- Match the actual implementation described in `docs/superpowers/specs/2026-07-12-unified-agent-flow-design.md`.
- Add no runtime dependency.
- Preserve responsive behavior at 1440×900 and 390×844.
- Do not modify Agent runtime code.

---

### Task 1: Replace the separated diagram

**Files:**
- Modify: `docs/design.html`

**Interfaces:**
- Consumes: Existing `.agent-blueprint` section and page design tokens.
- Produces: One semantic, connected diagram under `#agent-design`.

- [x] **Step 1: Replace the old three-panel HTML with the approved end-to-end flow**

Show request/authentication, deterministic route branches, each branch's real dependencies, answer composition, verification, audit, and response.

- [x] **Step 2: Replace obsolete panel CSS with connected-flow styles**

Use existing color tokens and visible arrows; distinguish Graph, LangChain, and trusted-code nodes by color.

- [x] **Step 3: Add responsive layout rules**

At `max-width: 720px`, stack the route branches and finish sequence and ensure `scrollWidth === clientWidth`.

- [x] **Step 4: Verify content and rendering**

Run `git diff --check`, parse the HTML, verify the required node names, and inspect desktop and mobile browser layouts.

- [x] **Step 5: Commit**

```bash
git add docs/design.html docs/superpowers/specs/2026-07-12-unified-agent-flow-design.md docs/superpowers/plans/2026-07-12-unified-agent-flow.md
git commit -m "Redraw unified agent execution flow"
```
