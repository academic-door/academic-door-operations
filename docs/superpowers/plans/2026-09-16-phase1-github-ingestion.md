# Phase 1 GitHub Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first automated, read-only GitHub ingestion slice for Academic Door Operations and stop at the exact account-permission boundary before scheduling.

**Architecture:** A stdlib REST client collects bounded GitHub organization evidence into `data/github-latest.json`; a pure snapshot builder merges that evidence with the Phase-0 baseline into `data/latest.json`; the existing validator/renderer then produces the private report. A manual-only workflow uses an Academic Door GitHub App installation token; CI uses fake data and never requires organization credentials.

**Tech Stack:** Python 3.11 standard library, GitHub REST API, GitHub Actions, `actions/create-github-app-token`.

**Spec:** `docs/superpowers/specs/2026-09-16-phase1-github-ingestion-design.md`

## Global Constraints

- Entire Academic Door scope is topology-dynamic.
- Cross-repository credentials are read-only.
- Never retrieve, log, persist, or display secret values.
- Unknown account facts remain `UNKNOWN`, never zero.
- No scheduled workflow until a manual credentialed probe succeeds.
- Product runtimes must not depend on Operations.

---

### Task 1: GitHub REST client and normalization primitives

**Files:**
- Create: `scripts/github_api.py`
- Create: `tests/test_github_api.py`

**Interfaces:**
- Produces `GitHubApi(token, base_url="https://api.github.com", opener=None)`.
- Produces `GitHubApi.get_json(path, params=None)` and `GitHubApi.get_paginated(path, item_key=None, params=None, max_pages=10)`.
- Produces `GitHubApiError(status, message, path)`.

- [ ] Write tests for Authorization header omission from errors, JSON GET, pagination, and HTTP error normalization using a fake opener.
- [ ] Run `python -m unittest tests.test_github_api -v` and verify RED.
- [ ] Implement the minimal stdlib client.
- [ ] Re-run the focused tests and verify GREEN.

### Task 2: Dynamic repository / Actions / billing / secret-metadata collector

**Files:**
- Create: `scripts/collect_github.py`
- Create: `tests/test_collect_github.py`

**Interfaces:**
- Consumes `GitHubApi`.
- Produces `collect_github(api, org, observed_at, run_window_days=14)` returning a JSON-serializable dict.
- Intermediate shape includes `repositories`, `actions`, `billing`, `credential_metadata`, and `gaps`.

- [ ] Write failing tests proving repository discovery is dynamic, Actions run summaries are bounded and `ESTIMATED`, successful billing is `ACTUAL`, 403 billing becomes `UNKNOWN`, and only secret metadata fields are retained.
- [ ] Run focused tests and verify RED.
- [ ] Implement installation-repository discovery, workflow/run aggregation, billing usage summary normalization, org/repo Actions secret metadata reads, and bounded gap capture.
- [ ] Re-run focused tests and verify GREEN.

### Task 3: Build normalized Operations snapshot

**Files:**
- Create: `scripts/build_snapshot.py`
- Create: `tests/test_build_snapshot.py`
- Modify: `schemas/operations-snapshot.schema.json`

**Interfaces:**
- Produces `build_snapshot(seed, github_evidence)`.
- Writes `data/latest.json` when invoked as CLI.
- Snapshot schema extends Actions entries with optional `run_count`, `estimated_minutes`, and `window_days`; credential entries may include optional `created_at`, `updated_at`, `storage_scope`, and `visibility`.

- [ ] Add failing tests for merge semantics, `UNKNOWN` billing preservation, dynamic repo Actions entries, and secret-value rejection.
- [ ] Run focused tests and verify RED.
- [ ] Extend schema with bounded optional fields without breaking Phase-0 seed validation.
- [ ] Implement the pure merge/builder and CLI.
- [ ] Re-run focused tests plus `python scripts/validate_snapshot.py data/seed-snapshot.json` and verify GREEN.

### Task 4: Manual-only credentialed probe workflow

**Files:**
- Create: `.github/workflows/operations-probe.yml`
- Modify: `README.md`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Uses repository variable `OPS_APP_CLIENT_ID` and secret `OPS_APP_PRIVATE_KEY`.
- Uses official `actions/create-github-app-token@v3` with owner `academic-door`.
- No `schedule` trigger.

- [ ] Add source-contract tests that assert the probe workflow is `workflow_dispatch` only, references the expected variable/secret, and does not commit/push.
- [ ] Run test suite and verify RED before the workflow exists.
- [ ] Add manual probe workflow: checkout, setup Python, mint App token, collect to `data/github-latest.json`, build `data/latest.json`, validate, render `reports/latest.md`, upload bounded artifacts.
- [ ] Update README with exact permission contract and explicit “do not schedule before probe acceptance” rule.
- [ ] Update CI to test all Python unit tests and validate/render both seed fixture behavior and generated fixture snapshot where applicable.
- [ ] Run all CI-equivalent commands and verify GREEN.

### Task 5: PR / CI / permission boundary checkpoint

**Files:** no product-code change unless CI exposes a defect.

- [ ] Open a PR linked to `#3` with the exact read-only permission contract.
- [ ] Wait for PR CI and fix any failures.
- [ ] Merge only after CI success and verify main CI/readback.
- [ ] Update `#3` with the accepted implementation state and exact remaining human-only GitHub App setup action.
- [ ] Do not activate a schedule until the Human Principal completes that action and a manual probe succeeds.
