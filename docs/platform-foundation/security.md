# Security

## Objective

Define the canonical security boundary for `Platform Foundation` so runtime execution, tool access, and write-capable workflows fail closed unless they are explicitly allowed by policy.

Owner: Platform Foundation.

## In Scope

- Kubernetes runtime baseline
- AWS read-only baseline
- Kubernetes RBAC read-only baseline
- network policy baseline
- secret handling baseline
- non-production write boundary

## Out of Scope

- product-specific Slack UX
- rollout metrics and dashboards
- prompt wording and agent reasoning
- provider implementation details outside the approved boundary

## Inputs and Dependencies

- `docs/platform-foundation/contracts.md`
- `docs/platform-foundation/runtime.md`
- `docs/platform-foundation/tool-layer.md`
- `backlog/openclaw-security-boundary.md`
- `docs/superpowers/plans/2026-04-13-platform-foundation-implementation-plan.md`

## Decisions

### Kubernetes Runtime Baseline

- dedicated namespace
- dedicated service account
- `runAsNonRoot: true`
- `allowPrivilegeEscalation: false`
- `readOnlyRootFilesystem: true`
- `seccompProfile: RuntimeDefault`
- drop all Linux capabilities
- explicit CPU / memory requests and limits

### AWS Baseline

- dedicated IRSA role
- no shared role with other workloads
- allow only `Get*` and `Describe*` families required by approved tools
- deny `Put*`, `Modify*`, `Delete*`, `Update*`, `Start*`, `Stop*`

### Kubernetes RBAC Baseline

- allow `get/list/watch` on `pods`, `pods/log`, `events`, `deployments`, `replicasets`, `nodes`
- deny `create/update/patch/delete`
- deny `exec`
- deny `port-forward`
- deny `secrets`

### Network Policy Baseline

Allow egress only to:

- Slack API
- LLM API endpoint
- Prometheus endpoint
- kube-apiserver
- AWS API endpoint

Default deny all other egress.

### Secret Handling

- use `ExternalSecrets`
- never place static credentials in pod spec
- redact API keys, bearer tokens, passwords, authorization headers, session tokens before reply

### Non-Production Write Boundary

- allowed only when `mode=non_prod_write`
- allowed environments: `staging`, `test`
- requires separate service account and separate IAM / RBAC policy set
- requires explicit approval marker in request contract
- every write action must emit audit event with actor, target, approval ref, and result
- write tool catalog must be separate from investigation tool catalog

## Validation Rules

- runtime workloads must satisfy the Kubernetes runtime baseline before any tool execution starts
- AWS access must remain read-only unless the request is explicitly authorized for non-production write
- Kubernetes RBAC must remain read-only for investigation flows
- network egress must fail closed for destinations outside the approved allowlist
- secrets must be sourced through `ExternalSecrets` and redacted before any reply is emitted
- write actions must be denied unless `mode=non_prod_write`, the environment is `staging` or `test`, and the request includes the required approval marker
- write-capable tools must not be exposed through the investigation tool catalog

## Deliverables

- One canonical security boundary document for `Platform Foundation`
- One explicit read-only boundary for runtime, IAM, RBAC, network, and secret handling
- One explicit non-production write boundary for controlled write workflows

## Exit Criteria

- `docs/platform-foundation/security.md` contains the runtime, AWS, RBAC, network, secret, and write boundary sections
- the file aligns with `contracts.md`, `runtime.md`, and `tool-layer.md`
- the boundary remains focused on platform security and does not drift into rollout or product workflow detail

## Open Questions

- None for this task; remaining environment-specific enforcement belongs in implementation documents and policies
