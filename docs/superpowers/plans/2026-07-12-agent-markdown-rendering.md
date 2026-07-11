# Agent Markdown Rendering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render safe, styled Markdown in Agent replies while leaving user messages, citations, ACL behavior, request flow, and smart autoscroll unchanged.

**Architecture:** Add a focused `MarkdownMessage` component backed by `react-markdown` and `remark-gfm`, then select it only for assistant messages in `Chat`. Keep raw HTML disabled, preserve React Markdown's safe URL transformation, and scope all typography to `.markdown-message`.

**Tech Stack:** React 18, TypeScript, `react-markdown`, `remark-gfm`, Testing Library, Vitest, CSS

## Global Constraints

- Render Markdown only for `assistant` messages.
- Keep `user` messages as plain React text.
- Do not enable `rehype-raw` or any equivalent raw-HTML processing.
- Links open in a new tab with `rel="noreferrer noopener"`; unsupported protocols remain non-actionable through React Markdown's default URL transform.
- Keep citations and activity markers outside the Markdown renderer.
- Do not change backend prompts, API contracts, ACL behavior, keyboard behavior, or smart autoscroll.
- Do not add syntax highlighting or an editor preview.
- Work directly on `main`, as requested by the user.

---

### Task 1: Add a safe Markdown message component

**Files:**
- Create: `frontend/src/components/MarkdownMessage.tsx`
- Create: `frontend/src/components/MarkdownMessage.test.tsx`
- Modify: `frontend/package.json`
- Modify: `frontend/pnpm-lock.yaml`

**Interfaces:**
- Consumes: `content: string`
- Produces: `MarkdownMessage({ content }: { content: string }): JSX.Element`

- [x] **Step 1: Add the rendering dependencies**

Run:

```bash
pnpm --dir frontend add react-markdown remark-gfm
```

Expected: `frontend/package.json` and `frontend/pnpm-lock.yaml` contain both production dependencies.

- [x] **Step 2: Write failing semantic and security tests**

Create `frontend/src/components/MarkdownMessage.test.tsx` with tests equivalent to:

```tsx
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { MarkdownMessage } from "./MarkdownMessage";

afterEach(cleanup);

it("renders Agent Markdown as semantic HTML", () => {
  const { container } = render(
    <MarkdownMessage content={"**重点**\n\n1. 第一步\n2. 第二步\n\n---\n\n| 项目 | 结果 |\n| --- | --- |\n| CI | 通过 |"} />,
  );

  expect(screen.getByText("重点").tagName).toBe("STRONG");
  expect(screen.getAllByRole("listitem")).toHaveLength(2);
  expect(container.querySelector("hr")).toBeInTheDocument();
  expect(screen.getByRole("table")).toBeVisible();
});

it("does not turn raw HTML into live elements", () => {
  render(<MarkdownMessage content={'<button onclick="alert(1)">危险</button>'} />);
  expect(screen.queryByRole("button", { name: "危险" })).not.toBeInTheDocument();
});

it("opens safe links in a separate tab", () => {
  render(<MarkdownMessage content="[内部文档](https://example.com/docs)" />);
  expect(screen.getByRole("link", { name: "内部文档" })).toHaveAttribute("target", "_blank");
  expect(screen.getByRole("link", { name: "内部文档" })).toHaveAttribute("rel", "noreferrer noopener");
});
```

- [x] **Step 3: Run the component test to verify RED**

Run:

```bash
pnpm --dir frontend exec vitest run src/components/MarkdownMessage.test.tsx
```

Expected: FAIL because `./MarkdownMessage` does not exist.

- [x] **Step 4: Implement the minimal safe renderer**

Create `frontend/src/components/MarkdownMessage.tsx`:

```tsx
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function MarkdownMessage({ content }: { content: string }) {
  return (
    <div className="markdown-message">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ children, href }) => (
            <a href={href} target="_blank" rel="noreferrer noopener">
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
```

Do not add `rehype-raw`, `dangerouslySetInnerHTML`, or a custom URL transform.

- [x] **Step 5: Run the focused component tests to verify GREEN**

Run:

```bash
pnpm --dir frontend exec vitest run src/components/MarkdownMessage.test.tsx
```

Expected: 3 tests pass with no warnings.

---

### Task 2: Integrate Markdown into Agent replies and style it

**Files:**
- Modify: `frontend/src/pages/Chat.tsx`
- Modify: `frontend/src/pages/Chat.test.tsx`
- Create: `frontend/src/markdown.css`
- Modify: `frontend/src/main.tsx`

**Interfaces:**
- Consumes: `MarkdownMessage({ content })` from Task 1
- Produces: assistant-only Markdown rendering inside the existing `.message.assistant` body

- [x] **Step 1: Write a failing Chat integration test**

Add a test that submits literal Markdown from the user and returns Markdown from the Agent:

```tsx
it("renders only Agent messages as Markdown", async () => {
  const send = vi.fn().mockResolvedValue({
    ...chatResult,
    answer: "**Agent 重点**",
  });
  const { container } = render(<Chat token="token" sendChat={send} />);

  fireEvent.change(screen.getByRole("textbox", { name: "问题" }), {
    target: { value: "**用户原文**" },
  });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));

  expect(await screen.findByText("Agent 重点")).toHaveProperty("tagName", "STRONG");
  expect(screen.getByText("**用户原文**")).toBeVisible();
  expect(container.querySelector(".message.user strong")).not.toBeInTheDocument();
});
```

- [x] **Step 2: Run the Chat test to verify RED**

Run:

```bash
pnpm --dir frontend exec vitest run src/pages/Chat.test.tsx
```

Expected: FAIL because the assistant text is still rendered by a plain `<p>`.

- [x] **Step 3: Select the renderer by message role**

Import `MarkdownMessage` in `Chat.tsx` and replace the shared message paragraph with:

```tsx
{message.role === "assistant" ? (
  <MarkdownMessage content={message.text} />
) : (
  <p>{message.text}</p>
)}
```

Leave `Citations` and `.activity` after this role-specific content block.

- [x] **Step 4: Add scoped Markdown typography**

Add `.markdown-message` rules to `frontend/src/markdown.css` and import it after `styles.css` in `frontend/src/main.tsx`:

```css
.markdown-message{line-height:1.8;overflow-wrap:anywhere}
.markdown-message>:first-child{margin-top:0}
.markdown-message>:last-child{margin-bottom:0}
.markdown-message p{margin:.65rem 0}
.markdown-message h1,.markdown-message h2,.markdown-message h3{margin:1.25rem 0 .6rem;font-family:var(--serif);line-height:1.25}
.markdown-message ul,.markdown-message ol{margin:.7rem 0;padding-left:1.5rem}
.markdown-message li+li{margin-top:.35rem}
.markdown-message blockquote{margin:1rem 0;padding:.7rem 1rem;border-left:3px solid var(--mint);background:rgba(168,230,193,.1);color:#495451}
.markdown-message hr{margin:1.25rem 0;border:0;border-top:1px solid var(--line)}
.markdown-message a{color:var(--forest);text-decoration-thickness:1px;text-underline-offset:.2em}
.markdown-message code{padding:.12rem .3rem;background:rgba(20,34,31,.08);font:.86em var(--mono)}
.markdown-message pre{max-width:100%;overflow-x:auto;padding:1rem;background:var(--ink);color:var(--paper-2)}
.markdown-message pre code{padding:0;background:transparent;color:inherit}
.markdown-message table{display:block;max-width:100%;overflow-x:auto;border-collapse:collapse}
.markdown-message th,.markdown-message td{padding:.55rem .7rem;border:1px solid var(--line);text-align:left}
.markdown-message th{background:rgba(168,230,193,.14);font-weight:600}
```

Remove or narrow `.message>div>p` only as needed so the existing user paragraph retains `margin:0`, `line-height:1.8`, and `white-space:pre-wrap`.

- [x] **Step 5: Run focused and full frontend verification**

Run:

```bash
pnpm --dir frontend exec vitest run src/components/MarkdownMessage.test.tsx src/pages/Chat.test.tsx
pnpm --dir frontend test -- --run
pnpm --dir frontend build
git diff --check
```

Expected: all tests pass, TypeScript/Vite production build succeeds, and the diff has no whitespace errors.

- [x] **Step 6: Commit the implementation**

```bash
git add frontend/src/pages/Chat.tsx frontend/src/pages/Chat.test.tsx frontend/src/markdown.css frontend/src/main.tsx docs/superpowers/plans/2026-07-12-agent-markdown-rendering.md
git commit -m "Render Agent replies as safe Markdown"
git push origin main
```

---

### Task 3: Rebuild and perform runtime acceptance

**Files:**
- Modify: `docs/superpowers/plans/2026-07-12-agent-markdown-rendering.md` (checkbox completion only)

**Interfaces:**
- Consumes: production frontend build from Tasks 1–2
- Produces: running Docker stack with browser-verified Markdown output

- [ ] **Step 1: Rebuild and restart the stack**

Run:

```bash
docker compose up -d --build
```

Expected: frontend, backend, ingest, and Postgres services are running; backend and Postgres are healthy.

- [ ] **Step 2: Perform browser acceptance**

Using `andy.admin`, submit a knowledge question that returns bold text and a list. Verify:

```text
Markdown markers such as ** are not visible
strong text is rendered as <strong>
list items are rendered as <li>
citation cards remain below the answer
the conversation remains pinned to the bottom while follow mode is active
```

- [ ] **Step 3: Run final verification**

```bash
pnpm --dir frontend test -- --run
pnpm --dir frontend build
docker compose ps
curl -fsS http://127.0.0.1:18000/health
curl -fsSI http://127.0.0.1:13000/ | head -n 1
git diff --check
```

Expected: 0 test failures, successful build, healthy services, backend `{"status":"ok"}`, frontend HTTP 200, and no whitespace errors.

- [ ] **Step 4: Record plan completion**

Mark all plan checkboxes complete, commit the plan-only change, and push `main`.
