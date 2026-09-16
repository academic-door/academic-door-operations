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

Tracked by #1. The initial deliverable is a normalized snapshot + deterministic private report that answers:

1. What does Academic Door cost now, and what is the projected period-end cost?
2. Where is that usage/cost coming from?
3. Which quotas/resources are pressured?
4. Which logical credentials exist and where are they used (metadata only)?
5. Which recurring workloads/services look inefficient or risky?
6. What requires Human Principal action now?

`data/seed-snapshot.json` is the first bounded inventory baseline. `scripts/render_report.py` renders a human-readable report. Account-level actual billing remains `UNKNOWN` until safe read-only provider access exists.