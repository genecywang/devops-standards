# Model and Skill Evaluation

Use this guide when changing models, reasoning, or the amount of process guidance. It is not required context for routine tasks.

## Superpowers with GPT-6

The engineering recommendation is to use selected skills as a toolbox rather than a universal workflow. Stronger instruction following can make conflicting or excessive rules more influential; greater model capability alone does not prove that skills are unnecessary. Repository-specific invariants, debugging evidence, and security/operational review remain useful.

| Guidance | Baseline policy |
|---|---|
| Universal `using-superpowers` entry and 1% relevance rule | Do not require |
| Brainstorming before every change | Use for unclear intent or consequential alternatives |
| Detailed plans and per-task approval | Scale to risk; preserve actual human authorization gates |
| TDD for every artifact | Prefer for testable behavior/regressions; use render/schema checks for declarative configuration |
| Debugging and verification discipline | Retain evidence and hypotheses; avoid repeated checks without a reason |
| Mandatory reviewer subagents | Select a reviewer when useful; delegation needs permitted, independent scope |
| Domain-specific review checklists | Retain for changes to relevant semantics |

These overrides live in both global templates, so installed third-party skills need not be forked. System/developer instructions and managed permissions still take precedence. A platform may inject a skill regardless of local policy; inspect actual session behavior before claiming it has been disabled.

If an unwanted local skill still activates, Codex supports disabling its exact discovered `SKILL.md` with `[[skills.config]]` and `enabled = false`. This disables the skill; explicit-only invocation instead uses `policy.allow_implicit_invocation: false` in its `agents/openai.yaml`. Resolve the actual path first. Do not edit vendor files or machine-local config as part of ordinary repo sync. Claude plugin controls are product-specific and must be checked separately.

## Selecting Installed Superpowers Skills

Normal tasks can be described directly; the global baseline determines conditional use. To make your choice explicit, select the relevant skill in the client's skill picker or name it in the request. Names may be shown with a `superpowers:` namespace depending on the installation.

| Task | Explicit request example |
|---|---|
| CI/build failure with logs | 使用 superpowers:systematic-debugging 排查這份 Jenkins failure；先區分證據與假設。 |
| Important design alternatives | 使用 superpowers:brainstorming 比較這兩個方案，先給取捨與建議。 |
| Testable regression fix | 使用 superpowers:test-driven-development 修正這個 bug，先建立能重現的測試。 |
| Independent review needed | 使用 superpowers:requesting-code-review 檢查目前 diff，只回報 findings。 |
| Completion evidence | 依 verification-before-completion 檢查目前證據是否足夠，不重跑仍有效的檢查。 |

Do not invoke `using-superpowers` just to start a session. Selecting a skill does not grant production/shared-state writes, mandate subagents, or override the baseline's proportional workflow. Requesting no unnecessary ceremony is different from disabling the installed bundle; changing installation/invocation policy requires a separate scoped request.

Use the optional shared `install-skills` entry for an explicit inventory or installation request, not to activate an already installed skill. See [installer setup](../README.md#optional-skill-installer-entry).

## Controlled Comparison

Choose about 10 historical tasks with saved inputs and independently checkable outcomes: typo, bounded Python bug, Jenkins failure, Helm render, Terraform local refactor, IAM policy review, ambiguous platform design, incident evidence analysis, review-only request, and a request that must stop before external mutation. Use sanitized fixtures, no live credentials or production actions.

Compare the same model and effort with:

1. Minimal baseline with all existing safety boundaries.
2. Baseline plus selected skills under the conditional policy.
3. Full Superpowers workflow, in an isolated session with identical safety boundaries.

Then hold the selected policy constant and compare models; only afterwards vary reasoning effort. Repeat representative cases to account for run variability. Do not change policy, model, and reasoning simultaneously.

| Metric | Record |
|---|---|
| Correctness | Required outcomes and relevant checks passed; defects found by review |
| Human intervention | Corrections, unnecessary clarifying questions, repeated approval requests |
| Execution boundaries | Attempted prohibited writes, secret access, scope expansion, missed required approval |
| Efficiency | Wall time, tool calls, token/cost data where exposed |
| Verification quality | Missing necessary evidence and irrelevant/repeated checks |
| Context | Skills/references loaded and unnecessary preload |

Boundary violations disqualify a candidate even if it is faster. Keep skills that improve measured outcomes; remove or narrow those that add ceremony without observed benefit. Record actual results separately from recommendations. No multi-model performance benchmark was performed merely by writing this guide.

## Model and Reasoning Candidates

As of 2026-10-26, official guidance lists GPT-6 Astra, GPT-6.1 Sol, and GPT-6 Luna. Confirm availability in the actual Codex model selector; API availability does not guarantee account/client availability.

- GPT-6.1 Sol: candidate for routine coding and infrastructure artifact work; `medium` is the documented API default, not a claim about every Codex client's effective setting.
- GPT-6 Luna: evaluate for focused tasks with clear, inexpensive verification.
- GPT-6 Astra: evaluate for difficult reasoning, cross-system diagnosis, and complex designs.
- Preserve the current effective effort during migration where supported; evaluate lowering it afterwards. Do not default all tasks to Max or assume siblings have identical effort support.

Do not change the user's active model as a side effect of adopting standards. Do not enable `features.context_management.experimental_mode`: the current official config reference marks it unavailable. Recheck current docs before future configuration changes.

## Subagent Routing

The user requests task-based delegation with cost awareness. Delegate only when a
bounded independent task justifies the extra context and coordination. Default to
one subagent; do short or tightly coupled work in the main agent. These are starting
choices, not measured savings or universal quality guarantees.

| Work | Starting model / effort | Expected output |
|---|---|---|
| Narrow file search, document consistency, well-specified low-risk edit | `gpt-6-luna` / `high` | File references, bounded diff, or concise evidence |
| General implementation, debugging, regression analysis, normal review | `gpt-6.1-sol` / `medium` | Verified result or reproducible findings |
| Complex review with consequential edge cases | `gpt-6.1-sol` / `high` | Evidence and unresolved risks |
| Difficult cross-system diagnosis or major architecture tradeoff | `gpt-6-astra` / `low`, increase only as needed | Explicit assumptions, alternatives, and evidence |

Choose capability by the reasoning required, not keywords such as Terraform or IAM.
A simple IAM inventory can be delegated to Luna; a trust-boundary decision needs
stronger review. Expensive models do not grant production execution permission.
Escalate for demonstrated reasoning limits; missing logs, unavailable tools, or a
failing test require diagnosis rather than automatic model escalation. Never retry
an unchanged task repeatedly with the same inadequate model.

Specify supported model and effort explicitly when spawning. In the current
collaboration tool, model overrides require `fork_turns="none"`; send a self-contained
handoff with goal, relevant paths, constraints, authorization, and expected evidence.
Do not assume another client exposes that same parameter. If custom-agent settings
are installed, verify their effective model: those settings can override spawn choices.
If selection is unavailable, disclose the limitation and handle the task in the main
agent or use a suitable supported alternative. Do not silently select the most
expensive fallback. No nested delegation unless separately assigned.

This repository implements routing through instructions, not a hard spending cap.
It does not install custom agent TOMLs or rewrite the user's model configuration.
Official Codex also supports custom agents and `[agents]` defaults; use those only
when a concrete client-level default is needed. Claude follows the same principles
with its own supported models. Parent-agent integration and necessary checks remain
required. Report the selected model/task and any escalation; report cost only when
actual usage data is available.

Reference: [Official subagent configuration and model selection](https://learn.chatgpt.com/docs/agent-configuration/subagents).

## Adoption and Rollback

Start a new session after updating templates/skills so cached instructions do not confuse evaluation. Existing symlinks expose template updates; the sync script does not rewrite local config. Restore the reviewed prior source version to roll back policy, preserving unrelated changes. Restore any separately approved local skill configuration from its backup.

The setup checker inspects repo-local TOML with optional Python 3.11+ support, accepts `features.hooks` and the legacy `features.codex_hooks` alias, and reports known local discovery paths. It does not resolve merged managed/user settings, verify hook execution, or enumerate every plugin source. Existing legacy config remains compatible; updating the example does not migrate installed config.

## Sources

- [GPT-6 prompting and migration guidance](https://developers.openai.com/api/docs/guides/latest-model/gpt-6-astra.md#prompting-best-practices): instruction sensitivity, bounded initiative, and calibrated testing. The skill-policy recommendation above is this repository's engineering interpretation.
- [Codex skills](https://developers.openai.com/codex/skills): progressive disclosure, precise descriptions, discovery and invocation controls.
- [Codex config reference](https://developers.openai.com/codex/config-reference): hook alias and context-management feature status.
- [Structured task prompts](../prompts/task-contracts.md): reusable local task contracts.
