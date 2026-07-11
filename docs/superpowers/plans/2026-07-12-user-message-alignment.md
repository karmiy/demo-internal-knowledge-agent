# User Message Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Anchor user messages to the right side of the conversation on desktop and mobile while keeping Agent messages left aligned.

**Architecture:** Preserve the existing message DOM and Agent grid. Override only `.message.user` with a right-starting reversed flex row so the `YOU` label sits at the far right and the bubble sizes to its content up to the existing `46rem` maximum. Keep the focused overrides in a small `chat-layout.css` file imported after the existing styles.

**Tech Stack:** React 18, CSS, Vitest, in-app browser acceptance

## Global Constraints

- Keep Agent rows unchanged and left aligned.
- Put the user bubble before the `YOU` label visually, with the label at the conversation's right edge.
- Keep the user bubble at or below `46rem` and prevent horizontal overflow.
- Preserve user bubble background, padding, and accent border.
- At `800px` and below, use a `3rem` role-label width and a flexible remaining bubble width.
- Do not change message DOM, Markdown rendering, citations, keyboard behavior, APIs, ACLs, or smart autoscroll.
- Work directly on `main`, as requested by the user.

---

### Task 1: Right-align user message rows

**Files:**
- Create: `frontend/src/chat-layout.css`
- Modify: `frontend/src/main.tsx`

**Interfaces:**
- Consumes: existing `.message.user > span` and `.message.user > div` DOM contract from `Chat`
- Produces: right-anchored user rows without changing component markup or state

- [x] **Step 1: Record the failing desktop layout**

In the running app at desktop width, read the conversation, user-row, user-bubble, and Agent-answer bounding boxes. Confirm the current failure:

```text
user row uses margin-left: 20%
user bubble is not anchored to the conversation's right side
YOU appears before the bubble on the left
```

- [x] **Step 2: Record the failing mobile layout contract**

At a viewport width below `800px`, confirm the existing mobile rule resets both message roles to `3rem minmax(0, 1fr)`, so the user label remains on the left.

- [x] **Step 3: Add the minimal desktop alignment override**

Create `frontend/src/chat-layout.css`:

```css
.message.user {
  display: flex;
  flex-direction: row-reverse;
  align-items: flex-start;
  margin-left: 0;
}

.message.user > span {
  flex: 0 0 4rem;
  text-align: right;
}

.message.user > div {
  width: fit-content;
  max-width: min(46rem, calc(100% - 5rem));
  overflow-wrap: anywhere;
}
```

- [x] **Step 4: Add the mobile width override**

Append:

```css
@media (max-width: 800px) {
  .message.user > span {
    flex-basis: 3rem;
  }

  .message.user > div {
    max-width: calc(100% - 4rem);
  }
}
```

- [x] **Step 5: Load the focused stylesheet last**

In `frontend/src/main.tsx`, import the new stylesheet after `styles.css` and `markdown.css`:

```tsx
import "./styles.css";
import "./markdown.css";
import "./chat-layout.css";
```

- [x] **Step 6: Run automated regression checks**

```bash
pnpm --dir frontend test -- --run
pnpm --dir frontend build
git diff --check
```

Expected: all frontend tests pass, TypeScript/Vite build succeeds, and no whitespace errors are reported.

- [x] **Step 7: Commit the implementation**

```bash
git add frontend/src/chat-layout.css frontend/src/main.tsx docs/superpowers/plans/2026-07-12-user-message-alignment.md
git commit -m "Align user messages to the conversation right"
git push origin main
```

---

### Task 2: Rebuild and verify responsive behavior

**Files:**
- Modify: `docs/superpowers/plans/2026-07-12-user-message-alignment.md` (checkbox completion only)

**Interfaces:**
- Consumes: the production frontend from Task 1
- Produces: a running, browser-verified desktop and mobile layout

- [ ] **Step 1: Rebuild the Docker stack**

```bash
docker compose up -d --build
```

Expected: all four services run; backend and Postgres are healthy.

- [ ] **Step 2: Verify desktop geometry**

At desktop width, confirm from element bounding boxes:

```text
user row right edge equals the conversation content right edge
YOU is to the right of the user bubble
user bubble right edge is to the right of the Agent answer's right edge for a short message
Agent row remains left aligned
```

- [ ] **Step 3: Verify mobile geometry**

At a viewport below `800px`, confirm:

```text
YOU remains to the right of the bubble
user bubble and row remain within the conversation bounds
Agent row remains left aligned
no horizontal page overflow is introduced
```

- [ ] **Step 4: Run final verification**

```bash
pnpm --dir frontend test -- --run
pnpm --dir frontend build
docker compose ps
curl -fsS http://127.0.0.1:18000/health
curl -fsSI http://127.0.0.1:13000/ | head -n 1
git diff --check
```

Expected: zero test failures, successful build, healthy services, backend `{"status":"ok"}`, frontend HTTP 200, and no whitespace errors.

- [ ] **Step 5: Record plan completion**

Mark all checkboxes complete, commit the plan-only change, and push `main`.
