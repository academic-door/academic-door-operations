# Academic Door Operations — latest snapshot

Observed at: `2026-09-16T14:50:00Z`
Scope: `ACADEMIC_DOOR_WIDE_TOPOLOGY_DYNAMIC`

## Cost / usage

| Service | Owner | Evidence | Amount | Status |
|---|---|---|---|---|
| GitHub Actions | parent-shared-cost-guardrail | UNKNOWN | UNKNOWN | account billing actual unavailable through current connector |
| Cloudflare runtime/scheduling | mixed-product-runtime | UNKNOWN | UNKNOWN | account billing not yet inventoried |
| AI / translation / enrichment providers | product-local-with-parent-cost-escalation | UNKNOWN | UNKNOWN | provider/account inventory incomplete |
| Email / domains / related recurring services | parent-shared-or-product-specific | UNKNOWN | UNKNOWN | account inventory incomplete |

## Quota / provider pressure

| Provider | Owner | Evidence | Remaining / Limit | Status |
|---|---|---|---|---|
| Semantic Scholar | daily-door | PROVIDER_REPORTED | UNKNOWN / UNKNOWN | PRESSURED |
| Elsevier | shared-policy-product-local-use | PROVIDER_REPORTED | UNKNOWN / UNKNOWN | HEALTHY |
| Crossref | product-local-public-provider-use | PROVIDER_REPORTED | UNKNOWN / UNKNOWN | HEALTHY |
| OpenAlex | product-local-public-provider-use | PROVIDER_REPORTED | UNKNOWN / UNKNOWN | HEALTHY |

## Credential metadata

| Logical credential | Provider | Owner | Consumers | Status |
|---|---|---|---|---|
| SEMANTIC_SCHOLAR_API_KEY | Semantic Scholar | daily-door | academic-door/econ-paper-monitor | configured; legitimate use observed; provider pressure present |
| ELSEVIER_API_KEY | Elsevier | shared-policy-product-local-use | academic-door/econ-paper-monitor, academic-door/journals | configured signal observed in Daily telemetry |
| ELSEVIER_INST_TOKEN | Elsevier | shared-policy-product-local-use | academic-door/econ-paper-monitor, academic-door/journals | configured signal observed in Daily telemetry |
| JINA_API_KEY | Jina | product-local-shared-capability-candidate | academic-door/econ-paper-monitor, academic-door/journals | workflow references known; account entitlement/cost unknown |

## Infrastructure / recurring services

| Service | Category | Owner | Evidence | Status |
|---|---|---|---|---|
| github-organization | source-control-ci-hosting | parent-shared | UNKNOWN | operational; account cost actual unavailable |
| cloudflare-current | runtime-external-scheduling | mixed-product-runtime | UNKNOWN | known configured surfaces; billing/usage account evidence pending |
| project-mailbox | email-infrastructure | parent-shared-or-product-specific | UNKNOWN | known project mailbox; recurring cost/plan not yet inventoried |

## GitHub Actions / recurring workloads

| Repository | Class | Evidence | Status |
|---|---|---|---|
| academic-door/econ-paper-monitor | high-frequency discovery / watchdog / update | ESTIMATED | primary Actions cost-attention surface |
| academic-door/nber-working-papers-pipeline | release detector / publication / health | ESTIMATED | post-acceptance quiescence optimization already accepted; continue bounded efficiency audit |
| academic-door/journals | monitor / history / deploy / health | ESTIMATED | bounded scheduled production and health surfaces |
| academic-door/longform-editorial | CI | ESTIMATED | currently light |
| academic-door/academic-door-composer | deploy / test / scheduled check-in | ESTIMATED | currently light; scheduled check-in dependency/value requires reconciliation |

## Human Principal actions

- Account-level read access will eventually be required to convert GitHub Actions, Cloudflare, AI/provider and other billed services from UNKNOWN/ESTIMATED to ACTUAL; do not request secret values.

> Secret values are never collected or displayed by this repository.
