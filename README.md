# Academic Door Operations

Public-safe Operations observability executor for Academic Door.

Canonical authority remains the private governance repository:
- checkpoint: `academic-door/academic-door-main-control#65`
- policy: `governance/OPERATIONS_OBSERVATORY.md`

Owner: `① Academic Door | 总控`

## Public-safe contract

This repository is intentionally public. It may execute read-only collection and publish a **sanitized aggregate** only.

The persistent public surface MUST NOT contain:

- credential logical names or credential inventory;
- private repository identifiers;
- private issue / pull-request pointers;
- Human account facts;
- payment-method, invoice, or private provider-account detail;
- raw private owner telemetry;
- secret values, authorization headers, cookies, private keys, passwords, or tokenized URLs.

Raw GitHub/account evidence may exist only transiently inside the GitHub Actions runner workspace and is never uploaded as an artifact.

Source systems remain authoritative: provider accounts, product owner runtimes, and the private canonical governance repository. This public repository is not a secret manager, account ledger, scheduler, broker, queue, cache, or product control plane.

## Public persistent outputs

The scheduled workflow publishes only:

- `public/latest.json` — strict allowlisted public snapshot;
- `public/latest.md` — human-readable public-safe report;
- `public/manifest.json` — hashes and file allowlist for the public artifact.

Artifact retention is seven days.

The report currently exposes only deliberately public-safe facts such as:

- coarse GitHub Actions billable state (`ZERO / POSITIVE / UNKNOWN`);
- public owner-provider health and public estimated DeepSeek cost;
- coarse service lifecycle;
- aggregate public-vs-private Actions workload pressure without private repository names;
- generic material alerts and human-action classes.

## Transient collection

The scheduled workflow writes raw collector outputs under `$RUNNER_TEMP/academic-door-operations`.

The GitHub collector may transiently see repository identifiers and organization billing details needed to compute aggregates. Those inputs are not persisted in this repository or its workflow artifact.

The owner-telemetry collector reads bounded public Academic Door evidence and may normalize fields that are later discarded by the public snapshot builder. Only the strict public schema may cross the persistence boundary.

## GitHub App

The workflow currently mints a short-lived read-only GitHub App installation token using:

- repository variable `OPS_APP_CLIENT_ID`;
- repository secret `OPS_APP_PRIVATE_KEY`.

Secret values are never emitted.

The public-safe implementation no longer calls GitHub Actions secret-metadata endpoints. A later separately approved account-permission step may remove now-unneeded `Secrets: Read` permissions from the GitHub App after production acceptance.

## Lifecycle example

Jina may be represented publicly as:

`RETIRING / RETIRE_BY_DEFAULT_PENDING_DAILY_PROVENANCE_GATE`

The public report does not publish private account context, credential metadata, or private owner pointers supporting that lifecycle decision.

## Development boundary

This repository can be public without making Academic Door private operational evidence public. Any future field added to the persistent snapshot must pass the strict allowlist validator and public-safety negative tests before merge.
