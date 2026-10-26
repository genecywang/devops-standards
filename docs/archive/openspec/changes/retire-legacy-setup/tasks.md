# Tasks

- [x] Record cleanup rationale and preserved compatibility paths.
- [x] Replace unsafe/outdated setup recipes and bootstrap prompt.
- [x] Narrow the installed Claude installer and retire its catalog-based hook behavior.
- [x] Move the two superseded plans and static catalog to Trash.
- [x] Validate OpenSpec, skill metadata, shell syntax, silent hook behavior, references, and diff; record results.

## Validation evidence

- Strict validation passed for `retire-legacy-setup`, `risk-matched-agent-workflow`, and the main `ai-coding-workflow` specification.
- Skill Creator metadata validation passed for `skills/install-skills`.
- `bash -n skills/install-skills/check-skills.sh` passed; executing the compatibility hook returned 0 with empty stdout/stderr.
- Confirmed all three retired artifacts absent, changed local Markdown links resolve, Codex/Claude shared global policy matches, and the existing Claude installer symlink still resolves.
- Reviewed active setup/skill/prompt text for stale bypass commands and catalog dependencies; remaining mentions describe retirement or supported legacy compatibility.
- `git diff --check` passed. No executable checker/sync logic changed in this cleanup, so their previously passing suites were not repeated. No live MCP setup, install, model benchmark, or infrastructure operation was performed.
- Deleted tracked artifacts were moved to macOS Trash with sandbox approval; Git history also preserves them. Machine-local configuration and third-party installations were not changed. No commit/push performed.
