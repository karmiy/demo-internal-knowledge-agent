# Chat Smart Autoscroll Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the chat conversation pinned to its newest content while the user remains near the bottom, without interrupting a user who scrolls upward to read history.

**Architecture:** Track the actual conversation element with a React ref and keep the follow/pause flag in a mutable ref so scroll events do not trigger renders. Recalculate the flag from a fixed `48px` bottom threshold and use a layout effect after message/status DOM updates to set the container to its current `scrollHeight` only when following is enabled.

**Tech Stack:** React, TypeScript, Testing Library, Vitest

## Global Constraints

- Work directly on `main`, as requested by the user.
- Use a bottom threshold of exactly `48px`.
- Follow on initial render, user messages, busy state, errors, Agent responses, citations, and activity markers.
- Pause when the user scrolls more than `48px` away from the bottom; resume when they return to `48px` or less.
- Use immediate `scrollTop` assignment, not smooth scrolling.
- Do not change request, thread, Enter/Shift+Enter, composition, citation, or ACL behavior.
- Do not add dependencies or a “back to latest” button.

---

### Task 1: Implement and verify smart bottom-follow behavior

**Files:**
- Modify: `frontend/src/pages/Chat.tsx`
- Modify: `frontend/src/pages/Chat.test.tsx`

**Interfaces:**
- Produces: `isNearBottom(element: HTMLElement) -> boolean` using `scrollHeight - scrollTop - clientHeight <= 48`
- Produces: a conversation element ref and mutable follow flag internal to `Chat`
- Consumes: existing `messages`, `busy`, and `error` render state

- [ ] **Step 1: Add failing scroll-behavior tests**

Add a test helper that defines writable `scrollTop` and configurable `scrollHeight`/`clientHeight` properties on `.conversation`. Use deferred `sendChat` promises to control busy and assistant updates.

Cover:

```text
bottom (distance 0) + assistant update -> scrollTop becomes latest scrollHeight
distance 49 + assistant update -> scrollTop remains unchanged
distance 48 + next content update -> follows to latest scrollHeight
scroll up, then return inside threshold, then update -> following resumes
```

Also verify the busy/loading render follows when enabled. Keep all existing keyboard and citation tests.

Run:

```bash
pnpm --dir frontend exec vitest run src/pages/Chat.test.tsx
```

Expected: FAIL because the conversation currently has no ref, scroll listener, or layout effect.

- [ ] **Step 2: Add the bottom-distance helper and refs**

In `Chat.tsx`, import `useLayoutEffect` and `useRef`, then add:

```typescript
const BOTTOM_THRESHOLD_PX = 48;

export function isNearBottom(element: HTMLElement) {
  return element.scrollHeight - element.scrollTop - element.clientHeight <= BOTTOM_THRESHOLD_PX;
}
```

Inside `Chat`, initialize `conversationRef` and `shouldFollowRef` with following enabled.

- [ ] **Step 3: Wire scroll tracking and post-render following**

Attach `ref={conversationRef}` and `onScroll` to `.conversation`. The handler updates only `shouldFollowRef.current` from `isNearBottom(event.currentTarget)`.

Add a `useLayoutEffect` with dependencies `[messages, busy, error]`. When following is enabled and the element exists, assign:

```typescript
element.scrollTop = element.scrollHeight;
```

Do not use `scrollIntoView`, `requestAnimationFrame`, timers, or smooth behavior.

- [ ] **Step 4: Run focused RED/GREEN verification**

```bash
pnpm --dir frontend exec vitest run src/pages/Chat.test.tsx
```

Expected: all Chat tests pass, including exact `48px` boundary and pause/resume cases.

- [ ] **Step 5: Run full frontend and production verification**

```bash
pnpm --dir frontend test -- --run
pnpm --dir frontend build
git diff --check
```

Expected: all frontend tests pass, TypeScript/Vite build succeeds, and diff check is clean.

- [ ] **Step 6: Commit, rebuild, and perform browser acceptance**

```bash
git add frontend/src/pages/Chat.tsx frontend/src/pages/Chat.test.tsx docs/superpowers/plans/2026-07-12-chat-smart-autoscroll.md
git commit -m "Keep active chats pinned to latest replies"
git push origin main
docker compose up -d --build
```

In a long conversation, verify visually that bottom-follow stays active, upward scrolling pauses it, and returning to the bottom resumes it. Leave all services running.
