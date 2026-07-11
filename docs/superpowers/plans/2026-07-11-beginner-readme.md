# Beginner-Friendly README Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Docker lifecycle instructions understandable and safe for readers who have not used Docker Compose before.

**Architecture:** Keep the README as the single user entry point. Replace the current terse quick-start section with an operation-first guide, while leaving the existing product, security, verification, network, and design sections intact.

**Tech Stack:** Markdown, Docker Compose

## Global Constraints

- Explain only the Docker concepts needed to operate this Demo.
- Put commands in the order a first-time user needs them.
- Clearly distinguish `stop`, `start`, `down`, and `down -v`.
- Preserve the existing port override and company-network guidance.

---

### Task 1: Rewrite the Docker quick-start and lifecycle guide

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: service names and port mappings from `docker-compose.yml`
- Produces: a beginner-oriented README section covering setup, start, status, access, logs, stop, restart, container removal, and data deletion

- [ ] **Step 1: Record the current documentation gap**

Run:

```bash
rg -n "docker compose (stop|start|down|logs|ps)" README.md
```

Expected: no matches, proving the current README does not explain day-to-day Docker operations.

- [ ] **Step 2: Replace the current `快速启动` section**

Update `README.md` so the section:

- briefly explains that Compose reads `docker-compose.yml` and manages the frontend, backend, Ingest Worker, and PostgreSQL together;
- uses `docker compose up -d --build` for the first launch and explains `-d` and `--build`;
- uses `docker compose ps` to verify service state;
- preserves the frontend and OpenAPI addresses plus port override instructions;
- uses `docker compose logs -f` and tells readers that `Ctrl+C` exits log viewing without stopping services;
- documents `docker compose stop` followed by `docker compose start` for normal pause/resume;
- documents `docker compose down` as removing containers and the Compose network while retaining the database volume;
- warns that `docker compose down -v` deletes local database data;
- retains the explanation of migration, seed, local embedding ingestion, and Claude usage.

- [ ] **Step 3: Verify command coverage and Markdown formatting**

Run:

```bash
rg -n "docker compose (up -d --build|ps|logs -f|stop|start|down|down -v)" README.md
git diff --check
docker compose config --quiet
```

Expected: all seven lifecycle commands are found, `git diff --check` produces no output, and Compose configuration exits successfully.

- [ ] **Step 4: Review the rendered content as a first-time user**

Confirm in order that the section answers:

1. What one command starts everything?
2. How do I know it started?
3. Where do I open the Demo?
4. How do I view and exit logs?
5. How do I stop and resume it?
6. Which command removes containers?
7. Which command deletes database data?

- [ ] **Step 5: Commit and push to the requested branch**

```bash
git add README.md docs/superpowers/plans/2026-07-11-beginner-readme.md
git commit -m "Clarify Docker usage for new users"
git push origin main
```

Expected: commit succeeds and `origin/main` points to the new commit.
