# Agent Markdown Rendering Design

## Goal

Render Markdown returned by the Agent as structured, readable conversation content without weakening the application's security boundary or changing user-message, citation, ACL, request, or autoscroll behavior.

## Scope

- Render Markdown only for `assistant` messages.
- Keep `user` messages as plain React text.
- Support paragraphs, emphasis, strong text, ordered and unordered lists, blockquotes, thematic breaks, links, inline code, fenced code blocks, and GitHub-flavored Markdown tables and task lists.
- Keep citations and activity markers outside the Markdown renderer in their existing positions.
- Add styles scoped to the Agent message body so document preview and other pages are unaffected.

## Rendering and Security

Use `react-markdown` with `remark-gfm`. Do not enable `rehype-raw` or any equivalent raw-HTML processing. React Markdown's normal element rendering remains the output boundary, so model-generated HTML is shown as text rather than inserted into the DOM.

Links use safe browser behavior: HTTP(S) links open in a new tab with `rel="noreferrer noopener"`. Unsupported link protocols are not made actionable. Code content is rendered as text; this Demo does not add syntax highlighting or executable code blocks.

## Components

Create a small `MarkdownMessage` component responsible for:

1. Receiving the Agent's text.
2. Passing it through the Markdown renderer with GFM enabled.
3. Applying safe link behavior.
4. Providing one stable CSS class for scoped typography.

`Chat` selects `MarkdownMessage` only for assistant messages and retains the current plain paragraph for user messages.

## Styling

Add scoped rules for paragraph rhythm, nested lists, headings, blockquotes, separators, links, inline code, preformatted blocks, and horizontally scrollable tables. Styles should inherit the existing editorial visual system and avoid changing the message grid or citation cards.

## Tests

Frontend tests verify:

- Agent `**strong**`, lists, and thematic breaks become semantic HTML.
- GFM tables render as tables.
- User-authored Markdown remains literal text.
- Raw HTML from an Agent is not inserted as a live element.
- Existing keyboard, citation, and smart-autoscroll tests remain green.

Production verification includes the complete frontend test suite, TypeScript/Vite build, Docker rebuild, and browser acceptance using a real Agent response containing Markdown.

## Non-Goals

- No raw HTML rendering.
- No syntax-highlighting dependency.
- No Markdown editor or preview in the composer.
- No backend prompt or response-format changes.
