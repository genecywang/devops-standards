# Codex Workflow Bootstrap Prompt

Use this prompt at the start of a new Codex session in this standards repository:

```text
請先檢查本 repo 的 Codex workflow bootstrap 狀態。

1. 執行 `scripts/check-codex-workflow.sh`。
2. 若缺少 `.codex/config.toml`、OpenSpec、必要 skills 或 validation scripts，先回報缺口與影響。
3. 只有在我明確同意後，才執行 `scripts/bootstrap-codex-workflow.sh`。
4. 若需要安裝 OpenSpec，使用 `scripts/bootstrap-codex-workflow.sh --install-openspec`，並說明會執行 `npm install -g @fission-ai/openspec@latest`。
5. 若我要同步個人 global Codex / Claude Code baseline，使用 `scripts/sync-personal-ai-config.sh --dry-run` 先預覽。
6. 只有在我明確同意後，才執行 `scripts/sync-personal-ai-config.sh` 或 `scripts/sync-personal-ai-config.sh --force`。
7. 安裝或初始化後，執行 `scripts/check-codex-workflow.sh`、`validations/all.sh`、`bash tests/sync-personal-ai-config.test.sh`，以及可用時的 `openspec validate bootstrap-codex-claude-workflow --strict`。

不要自動執行 Terraform apply、kubectl write、Helm release mutation、AWS write、secret access 或 production / shared-state 操作。
```

Expected outcome:

- Missing setup is reported before any installation.
- OpenSpec installation requires explicit approval.
- Personal global sync can be previewed with `--dry-run`.
- Existing global instruction files are not replaced unless `--force` is explicitly requested.
- The new session can verify readiness with `scripts/check-codex-workflow.sh`.
