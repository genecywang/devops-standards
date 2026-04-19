# Alert Auto Investigator — Company-Specific Assumptions

This document separates intentional company-specific behavior from the parts of
the system that are already stable enough to be treated as reusable core
contracts.

The goal is not to remove all customization. The goal is to make clear:

- which assumptions are intentionally local
- which assumptions should be abstracted further over time
- which contracts should remain stable across environments or organizations

---

## Company-Specific And Intentional

These assumptions are expected to vary between companies or clusters. They are
not design bugs by themselves and should stay in adapter, policy, or deployment
configuration layers.

### 1. Structured Slack Alert Format

The current Alertmanager and CloudWatch ingestion depends on a structured Slack
message contract.

Current examples:

- Alertmanager template emits `--- Structured Alert ---`
- CloudWatch Lambda Slack message emits a machine-readable block
- field names are fixed to the current parser contract

Why this is company-specific:

- another organization may use webhook JSON directly instead of Slack text
- another Alertmanager template may use different field names or section order
- some teams may never use CloudWatch-originated Slack alerts

Correct boundary:

- company-specific in ingress parser / normalizer layer

### 2. Environment Naming And Ownership

The current control pipeline assumes environment names such as:

- `dev-tw`
- `prod-jp`

It also assumes that `environment` is ownership-sensitive and must be stable.

Why this is company-specific:

- another company may use `staging`, `prod`, `prod-eu`, or account-based routing
- some teams may key ownership on cluster instead of environment
- some sources may not emit `environment` consistently

Correct boundary:

- company-specific in control policy and upstream alert labeling conventions

### 3. Cluster And Namespace Allowlisting

The current execution model relies on explicit runtime scope controls:

- `ALLOWED_CLUSTERS`
- `ALLOWED_NAMESPACES`

Why this is company-specific:

- allowed namespaces reflect organizational responsibility
- cluster ownership differs across teams
- some organizations prefer account / region gating before cluster gating

Correct boundary:

- company-specific in deployment config and runtime policy

### 4. Investigation Surface Is K8s-Oriented

The current supported investigation surface is intentionally workload-centric:

- `pod`
- `deployment`
- `job`
- `cronjob`

And intentionally avoids:

- host / infra metrics investigation
- cluster-wide freeform diagnosis
- AWS resource investigation beyond parse-only handling

Why this is company-specific:

- another organization may care more about node, EC2, RDS, or ALB investigation
- another team may want infra-first rather than workload-first routing

Correct boundary:

- company-specific in support matrix and tool registry priorities

### 5. Slack Thread As Primary Operator Surface

The current user-facing workflow assumes that:

- investigation replies live in Slack threads
- deterministic Slack text is the primary operator output

Why this is company-specific:

- another company may want ticketing, webhook callback, or incident timeline output
- another team may prefer ChatOps commands instead of passive thread replies

Correct boundary:

- company-specific in presentation layer and adapter layer

---

## Should Be Abstracted Further

These areas are currently workable, but still encode more local assumptions than
the long-term core should carry.

### 1. Parser Dependence On Current Label Vocabulary

The parser currently assumes upstream labels such as:

- `pod`
- `deployment`
- `cronjob`
- `job_name`
- `exported_job`
- `instance`

This is acceptable today, but still tightly coupled to current Prometheus rule
shape and Alertmanager template conventions.

Why more abstraction is needed:

- another environment may expose equivalent concepts under different labels
- one source may use `job_name`, another may use a provider-specific alias
- CloudWatch and Alertmanager already require different normalization paths

Desired direction:

- keep current parser behavior
- make source-specific mapping tables or source adapters more explicit

### 2. Resource Type Inference Still Reflects Local Monitoring Priorities

The current normalization rules intentionally map `instance` to `node`, not
`host`, because the investigation plane is K8s-oriented.

This is the correct current choice, but it is still an organizational semantic
decision rather than a universal truth.

Desired direction:

- preserve current `node` normalization in this deployment
- keep resource-type inference rules explicit and source-aware
- avoid embedding local semantics in places other than normalization / matrix docs

### 3. Alert Identity Still Depends On Current Alert Source Composition

Current `alert_key` shapes reflect current source contracts:

- Alertmanager keys include cluster, namespace when relevant, alert name, and resource name
- CloudWatch keys include account, region, and alarm name

This is good enough, but still tied to current source composition.

Desired direction:

- keep deterministic key generation
- document key strategy by source type
- avoid scattering key composition logic outside normalizers

### 4. OpenClaw Integration Shape Is Still Only Implied

The current system already separates deterministic investigation from future AI
assist, but the boundary is mostly captured in discussion and roadmap docs, not
yet as a formal integration contract.

Desired direction:

- formalize a read-only assist input / output schema before Phase 2 starts
- prevent future AI integration from re-introducing freeform routing or policy decisions

---

## Already Stable Core Contract

These parts are increasingly shaped like reusable system contracts rather than
organization-specific implementation detail.

### 1. Normalized Alert Event Model

The idea of converting heterogeneous ingress formats into a stable normalized
event model is reusable.

Stable qualities:

- source-agnostic event shape
- explicit `resource_type`
- explicit `resource_name`
- explicit `alert_key`
- explicit `environment`, `cluster`, `namespace` when available

What should remain stable:

- downstream code consumes normalized events, not raw Slack text

### 2. Deterministic Control Decision Model

The exact policy values are local, but the control model is stable:

- investigate
- skip
- deny / allow reasoning with explicit cause
- cooldown and rate-limit as deterministic gates

What should remain stable:

- control is a deterministic stage before investigation
- decisions are explainable and logged

### 3. Support Matrix Pattern

The specific supported resource types are local, but the pattern is reusable:

- `INVESTIGATE`
- `NEXT_CANDIDATE`
- `SKIP`

What should remain stable:

- support boundary is explicit
- unsupported does not silently become "best effort AI"

### 4. Deterministic Tool-Backed Investigation

The exact tools are local, but the architectural principle is stable:

- known resource type
- known tool mapping
- bounded execution scope
- deterministic reply formatting

What should remain stable:

- investigation is tool-backed first
- freeform AI does not replace fixed routing

### 5. Investigation Metadata Taxonomy

The current metadata model is already a strong reusable contract:

- `health_state`
- `attention_required`
- `resource_exists`
- `primary_reason`

What should remain stable:

- downstream reasoning layers consume metadata instead of reparsing summaries
- current-state outcome is separate from original alert wording

### 6. Golden Replay Framework

The fixture content is local, but the replay strategy is reusable.

What should remain stable:

- real alert shapes should be pinned by fixtures
- parser, formatter, dispatcher skip, handler behavior, and metadata contracts should be regression-tested with realistic payloads

---

## Practical Reading Guide

When a future change is proposed, classify it with these questions:

1. Does it change how this company labels or routes alerts?
   - keep it in adapter / policy / deployment config

2. Does it change a reusable contract between system stages?
   - treat it as a core design change and review carefully

3. Does it move local assumptions into shared core?
   - reject or refactor unless there is a strong cross-source reason

---

## Near-Term Implication

For the next implementation phases, this document implies:

- keep strengthening the stable core contracts already in place
- keep company-specific assumptions documented rather than hidden
- do not treat current local policy choices as globally correct defaults
- formalize OpenClaw read-only assist only after the current stable contracts are trusted
