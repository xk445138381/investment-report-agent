# Launch Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the investment report agent to a locally verifiable launch-candidate state with accurate docs, repeatable checks, and a clear readiness report.

**Architecture:** Keep the current FastAPI backend and Next.js frontend. Do not add new product scope; focus on launch blockers: stale documentation, missing check commands, unclear environment requirements, and unverified runtime behavior.

**Tech Stack:** Python 3.12, FastAPI, pytest, Next.js 16, React 19, Playwright, PowerShell.

---

### Task 1: Correct Launch Documentation

**Files:**
- Modify: `README.md`
- Modify: `frontend/README.md`

- [ ] Replace stale "early development / stub" status with current launch-candidate status.
- [ ] Document correct backend startup command: `cd backend; $env:PYTHONPATH="src"; python -m uvicorn api.main:app --host 127.0.0.1 --port 8000`.
- [ ] Document frontend startup command: `cd frontend; npm run dev`.
- [ ] Document verification commands: backend unit, frontend lint/build, smoke e2e.
- [ ] Document known launch limitations: external data/LLM keys required; AkShare may be blocked by proxy; MongoDB optional.

### Task 2: Add Launch Check Script

**Files:**
- Create: `scripts/launch_check.py`

- [ ] Run backend unit tests from `backend`.
- [ ] Run frontend lint from `frontend`.
- [ ] Run frontend production build from `frontend`.
- [ ] Run frontend smoke e2e from `frontend`.
- [ ] Exit non-zero if any command fails.

### Task 3: Add Launch Readiness Report

**Files:**
- Create: `docs/launch-readiness-2026-06-05.md`

- [ ] Record environment versions.
- [ ] Record command results and exit codes.
- [ ] Record runtime verification status for quick scan and value deep dive.
- [ ] Record remaining limitations and launch decision.

### Task 4: Verify

**Commands:**
- `python scripts/launch_check.py`

**Expected:**
- Backend unit tests pass.
- Frontend lint passes.
- Frontend build passes.
- Smoke e2e passes.
