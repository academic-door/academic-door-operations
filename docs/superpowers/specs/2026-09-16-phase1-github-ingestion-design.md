# Phase 1 GitHub ingestion design

Status: approved direction under `academic-door-operations#3` and `academic-door-main-control#65`.
Owner: `① Academic Door | 总控`.

## Goal

Automate the GitHub-facing part of Academic Door Operations with a read-only, topology-dynamic collector that can discover current organization repositories, summarize Actions activity, attempt authoritative organization billing reads, inventory Actions secret metadata without retrieving values, and produce normalized snapshot inputs for the existing private report.

## Boundaries

- Entire Academic Door organization scope; no hard-coded numbered-Brain boundary.
- Read-only GitHub App installation access. No repository write permission is granted to the App.
- Operations writes generated reports only with its own repository `GITHUB_TOKEN`; the cross-repository App token is read-only.
- Never retrieve or persist secret values. GitHub Actions secret APIs are metadata-only and return names/timestamps/visibility, not encrypted values.
- If an endpoint is unavailable or lacks permission, emit `UNKNOWN`/capability-gap evidence rather than fail closed or guess zero.
- No Academic Door product/runtime depends on Operations availability.
- No daily schedule is activated until the required read-only App credentials are configured and a manual probe succeeds.

## Minimum GitHub App permission contract

Repository permissions:
- Metadata: read (GitHub App baseline metadata access).
- Actions: read — enumerate workflows/runs for private repositories.
- Contents: read — read bounded owner telemetry/config files when a later adapter needs them.
- Secrets: read — list repository Actions secret metadata only; values are never exposed by the API.

Organization permissions:
- Administration: read — required for organization billing usage endpoints.
- Secrets: read — list organization Actions secret metadata only.

Repository access: install on **all repositories** in `academic-door` so newly created repositories enter scope automatically. The App is not installed outside the Academic Door organization.

## Authentication

The Operations workflow will use GitHub's official `actions/create-github-app-token` action. Store only:
- repository variable `OPS_APP_CLIENT_ID`;
- repository secret `OPS_APP_PRIVATE_KEY`.

The private key is used only to mint short-lived installation tokens. Generated installation tokens are ephemeral and masked by GitHub Actions.

## Collector components

1. `scripts/github_api.py`
   - stdlib HTTPS client;
   - JSON GET only;
   - pagination helper;
   - typed API error carrying status/body without leaking auth headers.

2. `scripts/collect_github.py`
   - list installation repositories;
   - for each repository, list workflows and bounded recent runs;
   - aggregate run counts, conclusions, and estimated wall-clock duration as `ESTIMATED` evidence;
   - attempt organization billing usage summary for GitHub Actions; successful provider/account response becomes `ACTUAL`, permission/platform failure becomes `UNKNOWN` with a reason;
   - list organization and repository Actions secret metadata, storing names/timestamps/visibility only;
   - produce `data/github-latest.json` as a bounded intermediate artifact.

3. `scripts/build_snapshot.py`
   - combine Phase-0 seed baseline with GitHub intermediate evidence;
   - replace GitHub Actions cost/action/credential metadata with fresher observed evidence;
   - preserve non-GitHub Phase-0 entries until their provider adapters exist;
   - write `data/latest.json` conforming to `schemas/operations-snapshot.schema.json`.

4. `.github/workflows/operations-probe.yml`
   - manual only (`workflow_dispatch`) until credentials are verified;
   - mint read-only App installation token;
   - collect GitHub evidence, build/validate snapshot, render report;
   - upload report/snapshot as workflow artifacts for verification;
   - no commit/push and no schedule in the probe stage.

After a successful manual probe, a separate change may enable daily refresh and bounded history. That activation is not bundled with initial credential setup.

## Failure behavior

- Authentication missing: workflow does not run automatically; manual probe fails clearly before collection.
- One repository endpoint fails: capture a bounded gap and continue other repositories where safe.
- Billing endpoint 403/404/not supported: cost remains `UNKNOWN`; repository Actions evidence still renders.
- Secret metadata endpoint unavailable: credential metadata remains known from existing registry/workflow references, with storage timestamps/scope marked unavailable.
- Unexpected JSON/API failures fail the probe so they are fixed before scheduling.

## Testing

Unit tests use fake HTTP responses only; CI must never require organization credentials.
Tests cover pagination, API error handling, billing normalization, secret-value exclusion, dynamic repository aggregation, and snapshot merge behavior.

Acceptance for this slice: code and CI are green, manual workflow is present but unscheduled, and the only remaining blocker is the Human Principal creating/installing the explicitly-scoped read-only GitHub App and adding its client ID/private key to the Operations repository.