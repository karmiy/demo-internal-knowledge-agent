# User Message Alignment Design

## Goal

Place user-authored messages on the right side of the conversation while keeping Agent messages on the left, preserving the existing editorial style and all chat behavior.

## Root Cause

The current rule, `.message.user { margin-left: 20%; }`, only offsets the user row from the left. It does not anchor the row to the conversation's right edge, so the message appears near the middle on wide screens.

## Layout

- Keep Agent rows unchanged: role label first, answer content second, left aligned.
- Reverse only the user row's grid tracks: message bubble first and `YOU` label second.
- Right-justify the user row's grid tracks within the full conversation width.
- Keep the bubble's existing maximum width of `46rem`, background, padding, and accent border.
- Right-align the `YOU` label so its relationship to the user bubble is visually clear.
- On viewports at or below `800px`, keep the same right-side ordering with a flexible bubble track and a `3rem` role-label track.

## Scope

The change is CSS-only. It does not alter message DOM, Markdown rendering, citations, keyboard behavior, API requests, ACL behavior, or smart autoscroll.

## Verification

- Add a Chat regression test that verifies the user and assistant role classes remain distinct and retain the expected DOM ordering contract used by CSS.
- Run the complete frontend test suite and production build.
- In browser acceptance, compare user and Agent bounding boxes at desktop width and confirm the user bubble is closer to the conversation's right edge while the Agent answer remains left aligned.
- Repeat at mobile width and ensure neither message overflows horizontally.
