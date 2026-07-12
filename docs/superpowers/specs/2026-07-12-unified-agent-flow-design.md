# Unified Agent Flow Design

## Goal

Replace the separated LangGraph, LangChain, and trusted-code panels with one connected, end-to-end diagram showing how a user question travels through the current application.

## Flow

1. The browser sends the question, JWT, and `thread_id` to FastAPI.
2. FastAPI authenticates the actor and verifies thread ownership.
3. LangGraph enters `route_query`, whose Python keyword logic selects `documents`, `employee_data`, or `mixed`.
4. `retrieve_documents` calls ACL-aware document search, `LocalHashEmbeddings`, and pgvector.
5. `query_employee_data` calls application-owned salary policy and `get_salary`; it does not call a LangChain node.
6. `mixed` runs document retrieval and employee-data lookup in sequence.
7. All branches merge at `compose_answer`, which creates LangChain messages and invokes `ChatAnthropic` only when authorized evidence exists.
8. `verify_answer` validates citations, `audit_run` records the result, and FastAPI returns the response to the browser.

## Visual Rules

- Present all steps inside one connected diagram.
- Use coral for LangGraph nodes, mint for LangChain components, and yellow for trusted application/data code.
- Place called dependencies inside or immediately beside the Graph node that invokes them.
- Explicitly label `query_employee_data` as not using LangChain.
- Preserve the existing editorial dark-green visual language.
- Collapse branch columns and horizontal sequences into a readable single-column flow below 720 px without horizontal overflow.

## Scope

Only `docs/design.html` changes. Runtime code, APIs, dependencies, and Docker services remain unchanged.
