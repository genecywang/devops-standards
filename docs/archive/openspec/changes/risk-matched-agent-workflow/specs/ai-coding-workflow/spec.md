# ai-coding-workflow Delta Specification

## MODIFIED Requirements

### Requirement: OpenSpec as planning layer

The repository SHALL use OpenSpec for agent policy, approval gates, validation semantics, cross-module design, and risky infrastructure changes. Small, bounded behavior fixes MAY use a short intent, scope, and verification record unless local rules require OpenSpec.

#### Scenario: Workflow policy changes

- GIVEN a change alters agent behavior or authorization semantics
- WHEN implementation begins
- THEN an OpenSpec proposal, specs, design, and tasks SHALL exist

#### Scenario: Bounded local fix

- GIVEN a fix has clear requirements, limited scope, no interface or permission change, and no significant operational risk
- WHEN the agent implements it
- THEN it MAY proceed with a short task record and relevant verification without a new OpenSpec change

### Requirement: Conditional skill loading

The repository SHALL select skills by task intent and semantic impact, not keywords alone. Superpowers SHALL be optional; user baseline rules SHALL override conflicting skill guidelines without overriding platform permissions.

#### Scenario: Conceptual question or typo

- GIVEN a task explains IAM concepts or fixes a Helm README typo
- WHEN the agent selects skills
- THEN it SHALL NOT require a domain change review solely because those technology names appear

#### Scenario: Explicit bounded implementation

- GIVEN the user has authorized a clear local task
- WHEN a generic skill requires universal brainstorming, design approval, or mandatory delegation
- THEN the agent SHALL apply the baseline's conditional triggers and continue authorized work

#### Scenario: Security or operational semantics change

- GIVEN a change modifies permissions, trust boundaries, infrastructure behavior, or deploy/rollback paths
- WHEN preparing or reviewing it
- THEN the agent SHALL use the relevant domain review skill

### Requirement: Human approval for shared-state writes

The repository SHALL prevent AI agents from autonomously performing operations that mutate production or shared infrastructure state. Explicit approval SHALL cover the exact target and scope; an existing valid approval SHALL NOT require repeated confirmation for that same operation.

#### Scenario: Terraform apply is needed

- GIVEN implementation requires `terraform apply` and no explicit approval covers that target and scope
- WHEN the agent reaches execution
- THEN it SHALL stop before the write
- AND it SHALL explain the risk and impact scope
- AND it SHALL wait for explicit human approval while continuing independent authorized local preparation

#### Scenario: Local validation is needed

- GIVEN implementation requires lint, test, render, dry-run, or static validation
- WHEN the command is local and non-destructive
- THEN the agent MAY run it without additional approval

### Requirement: Evidence before completion

The repository SHALL require relevant validation evidence before completion claims, commits, or PR handoff. Verification SHALL match the change's risk and SHALL NOT be broadened or repeated without a new change, failure, or unresolved concern.

#### Scenario: Relevant checks pass

- GIVEN checks cover the changed behavior and required project checks pass
- WHEN no new code or unresolved concern invalidates the evidence
- THEN the agent SHALL proceed to delivery without repeating unrelated checks

#### Scenario: Validation is unavailable or limited

- GIVEN a tool is missing or a check only validates syntax
- WHEN the agent reports results
- THEN it SHALL disclose the skipped check or limitation rather than claim semantic safety

## ADDED Requirements

### Requirement: Preparation and authorization are distinct

The agent SHALL distinguish execution environment, target environment, review readiness, and human execution approval. Existing approval-required operations SHALL remain gated.

#### Scenario: Local production artifact preparation

- GIVEN the user authorizes a local chart or IAM policy change without deployment approval
- WHEN the agent prepares a diff and static validation
- THEN it SHALL continue the authorized preparation
- AND it SHALL wait for explicit approval before any gated external mutation
- AND a review's ready conclusion SHALL NOT grant that approval

### Requirement: Setup inspection is compatible and non-destructive

The checker SHALL parse TOML settings, recognize current and legacy hook keys, treat Superpowers as optional, and avoid exposing unrelated configuration values.

#### Scenario: Current hook setting exists

- GIVEN local config enables `features.hooks`
- WHEN setup is checked
- THEN the checker SHALL report the local hook flag as enabled
- AND an explicit current flag SHALL take precedence over the legacy alias

#### Scenario: Optional bundle is absent

- GIVEN Superpowers is absent or installed via a supported alternative discovery path
- WHEN setup is checked
- THEN absence SHALL NOT cause a missing-dependency warning or failure
- AND a discovered path SHALL NOT be described as proof of activation

#### Scenario: Config cannot be parsed

- GIVEN Python TOML support is unavailable or config is invalid
- WHEN setup is checked
- THEN inspection SHALL be reported as skipped or failed without printing config contents

### Requirement: Outcome-based task contracts and evaluation

The repository SHALL provide reusable prompts describing goals, relevant context, constraints, deliverables, and observable completion criteria. Infrastructure tasks SHALL identify execution and target environments and authorization boundaries.

#### Scenario: Structured prompt adoption

- GIVEN a user selects a task template
- WHEN completing its fields
- THEN unnecessary fields MAY be omitted and routine execution steps SHALL remain agent decisions
- AND source material SHALL be distinguished from instructions


#### Scenario: Global baseline structures a new task

- GIVEN a new session loads the global baseline and receives a multi-step development, infrastructure, incident, or review task
- WHEN the user describes the task in natural language
- THEN the agent SHALL organize the goal, relevant context, constraints, deliverable, and completion criteria from available information
- AND infrastructure tasks SHALL distinguish execution environment, target environment, and authorization
- AND the agent SHALL ask only about consequential missing information without inventing authorization
- AND it SHALL NOT require a user-filled template, a template file path, or an extra approval gate for a clear authorized task
- AND simple questions, typo fixes, and formatting-only edits SHALL NOT require the full structure
- AND the structure need not be displayed unless useful to clarify scope

#### Scenario: Model or Superpowers comparison

- GIVEN a proposed model, reasoning, or skill-policy change
- WHEN evaluating it
- THEN representative tasks SHALL compare quality, intervention, time, and boundary compliance while changing one factor at a time
- AND unperformed evaluations SHALL NOT be reported as measured improvements
