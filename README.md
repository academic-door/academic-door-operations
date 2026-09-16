# Academic Door Operations

Private Parent-held operations / FinOps observability for the entire Academic Door project.

Canonical authority: `academic-door/academic-door-main-control`
- checkpoint: `academic-door/academic-door-main-control#65`
- policy: `governance/OPERATIONS_OBSERVATORY.md`

Owner: `① Academic Door | 总控`

## Scope

This repository is **Academic Door-wide and topology-dynamic**. It tracks material operating cost, resource usage, quota/rate pressure, credential metadata, infrastructure/services, GitHub Actions efficiency, and Human Principal attention requirements across all current and future Academic Door products, channels, runtimes, providers, APIs, and shared capabilities.

Current numbered Brains/repositories are only the present inventory. They do not define the scope.

## Hard boundaries

- Read-only observability; not a product control plane.
- Never store secret values, authorization headers, cookies, private keys, mailbox passwords, or tokenized URLs.
- Product/runtime systems must not depend on this repository to operate.
- Raw/high-cardinality owner telemetry remains in the owning repository/runtime; this repo stores bounded normalized summaries and evidence pointers.
- Unknown billing/quota facts stay `UNKNOWN`; they are never silently treated as zero.

## Evidence classes

- `ACTUAL`: authoritative billed amount or metered usage.
- `PROVIDER_REPORTED`: provider-reported quota/rate/remaining/reset state.
- `ESTIMATED`: derived from repository/runtime evidence when authoritative billing is unavailable.
- `UNKNOWN`: not currently observable.

## Phase 0

Tracked by #1 and accepted on main. `data/seed-snapshot.json` is the bounded initial inventory baseline. `scripts/render_report.py` renders a human-readable private report.

## Phase 1 — automated read-only ingestion

Tracked by #3. The first automated slice is GitHub-wide observation:

- discover repositories from the Academic Door GitHub App installation rather than hard-coding today's product list;
- summarize recent Actions workflow activity as `ESTIMATED` operational evidence;
- read organization billing usage as `ACTUAL` only when GitHub exposes it through the authorized billing endpoint;
- inventory GitHub Actions secret **metadata only** (logical names, timestamps, visibility/scope), never secret values;
- merge the observed evidence into `data/latest.json` and render `reports/latest.md`.

The first live manual probe was accepted on 2026-09-16: workflow run `35131360875` completed successfully on `main`, including App-token minting, Academic Door-wide collection, normalized snapshot validation, report rendering, and bounded artifact upload. That acceptance permits one bounded daily read-only run. The workflow remains manually dispatchable as well.

### Academic Door Operations GitHub App — minimum permission contract

Install the App only on the `academic-door` organization and select **All repositories** so future Academic Door repositories enter scope automatically.

Repository permissions:

- **Metadata: Read** (baseline GitHub App repository metadata access)
- **Actions: Read**
- **Secrets: Read** — metadata only; GitHub's list/get secret endpoints do not reveal encrypted values

Organization permissions:

- **Administration: Read** — required for organization billing usage endpoints
- **Secrets: Read** — organization Actions secret metadata only

No repository or organization write permission belongs in this App. `Contents: Read` is also intentionally not requested yet because this GitHub slice does not read repository files; if a later owner-telemetry adapter needs it, that permission must be added through a separate reviewed change.

The workflow expects:

- repository variable `OPS_APP_CLIENT_ID`;
- repository secret `OPS_APP_PRIVATE_KEY`.

`actions/create-github-app-token@v3` uses those to mint a short-lived installation token. Cross-repository reads use that token; report generation itself does not grant the App any write path.

### Activation state

1. Collector/probe implementation merged with CI green. ✅
2. Human Principal created and installed the least-privilege App and configured the variable/secret. ✅
3. Live manual probe run `35131360875` succeeded. ✅
4. Bounded artifacts and account-level billing permission were verified. ✅
5. Daily read-only report schedule with 30-day artifact retention is the accepted next slice.

Account-level GitHub Actions billing is now observable as `ACTUAL` when the billing API responds successfully; `UNKNOWN` remains mandatory for any unavailable provider/account surface.
