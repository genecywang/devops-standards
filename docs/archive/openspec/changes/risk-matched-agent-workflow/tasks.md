# Implementation plan

- [x] 1. Record approved scope and behavioral scenarios before editing implementation.
- [x] 2. Add failing isolated checker tests for current/legacy hooks, optional skill discovery, and safe config diagnostics.
- [x] 3. Update dual-agent baselines, workflow/spec rules, and three review skills; preserve write gates.
- [x] 4. Implement checker changes and update Codex examples without rewriting machine-local config.
- [x] 5. Add structured task prompts and model/Superpowers evaluation guidance, with official sources and limitations.
- [x] 6. Run `python3 -m unittest discover -s tests -p 'test_*.py'`, `bash tests/sync-personal-ai-config.test.sh`, shell syntax checks for each script, `scripts/check-codex-workflow.sh`, `openspec validate risk-matched-agent-workflow --strict`, and `git diff --check`.
- [x] 7. Review behavioral scenarios and final diff; record results and remaining limitations. Archive only after acceptance.

No infrastructure write, global configuration write, credential access, or deployment is authorized by these tasks.

Validation and scenario-review evidence: [validation.md](validation.md).

- [x] 8. Add approved global task-structuring rules to both templates; verify aligned policy, strict OpenSpec validation, and diff.
