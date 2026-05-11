# CLAUDE.md（devops-standards Repository）

本 repo 是 DevOps / Platform Engineering AI workflow standards 的 source of truth，用來追蹤與分發 Codex / Claude Code 規範、OpenSpec artifacts、conditional skills、workflow playbooks 與 validation scripts。它不是一般 consumer project。

## 回覆與工作風格

- 一律使用繁體中文回覆，技術術語保留英文原文。
- 中文與英文 / 數字間加半形空格。
- 以工程判斷為主，不迎合；方案有問題時直接指出並提供替代方案。

## Repository 目標

- Codex-first，Claude Code-compatible。
- `templates/codex/AGENTS.global.md` 是個人 global Codex baseline，適合 symlink 到 `~/.codex/AGENTS.md`。
- `templates/claude/CLAUDE.global.md` 是個人 global Claude Code baseline，適合 symlink 到 `~/.claude/CLAUDE.md`。
- Root `AGENTS.md` / `CLAUDE.md` 只描述如何維護本 standards repo；不要把它們當成 consumer repo 模板。
- Consumer repo 若要採用這套規範，應複製或安裝 `templates/`、`skills/`、`workflows/`、`validations/` 中需要的部分，並在該 repo 內 review。

## 維護原則

- 調整 agent 行為、workflow、approval gate、validation semantics 時，先更新或建立 `openspec/changes/<change-id>/`。
- 同步更新 Codex 與 Claude Code 相關模板，避免兩邊規範漂移。
- 保持 global templates 精簡；詳細流程放 `workflows/`，判斷型 checklist 放 `skills/`，可重跑檢查放 `validations/`。
- 不要把 machine-local config、secret、credential、personal token、absolute home path 寫入可提交檔案。
- `.codex/config.toml` 與 `.claude/settings.local.json` 是本機檔案，不進 git。

## Personal Sync

個人快速同步使用：

```zsh
scripts/sync-personal-ai-config.sh
```

此腳本會建立：

- `~/.codex/AGENTS.md -> templates/codex/AGENTS.global.md`
- `~/.claude/CLAUDE.md -> templates/claude/CLAUDE.global.md`
- `~/.codex/skills/gene-devops-* -> skills/*`

預設不覆蓋既有檔案；需要替換時使用 `--force`，腳本會先產生 `.bak.<timestamp>`。

## OpenSpec Workflow

主要流程：

```text
proposal -> specs -> design -> tasks -> implementation -> validation -> review -> archive
```

OpenSpec 負責 intent、requirements、design decisions、tasks。它不授權 agent 執行 production 或 shared-state 寫入。

## 操作邊界

可直接執行：

- 唯讀檢查、`rg`、讀檔、diff、lint、test、dry-run、format。
- 本機 workspace 內檔案編輯與程式碼生成。
- `terraform fmt`、`terraform validate`、`terraform plan`。
- `helm lint`、`helm template`。
- Kubernetes manifest static validation，例如 `kubeconform`、`kubectl --dry-run=client`。

執行前需說明風險與影響範圍，並取得人工 approval：

- `terraform apply`、`terraform destroy`、`terraform import`、`terraform state mv/rm`。
- `kubectl apply/delete/edit/patch/rollout`。
- `helm upgrade/install/uninstall/rollback`。
- AWS 寫入操作，尤其 IAM、RDS、KMS、S3 policy、Security Group、Route53。
- Production / shared environment deploy、rollback、migration。
- 權限變更、secret rotation、credential 存取。

禁止直接執行：

- `git push --force`。
- 刪除 production resource。
- 修改或輸出 secret / credential。
- 未經確認的 `git reset --hard`、`git clean -f`、`git branch -D`、`sudo`。

macOS 本機刪除優先使用 `trash`，不用 `rm`。

## Validation

依變更類型執行：

| 類型 | 建議驗證 |
|---|---|
| Shell scripts | `bash -n scripts/*.sh validations/*.sh tests/*.sh` |
| Personal sync | `bash tests/sync-personal-ai-config.test.sh` |
| Workflow setup | `scripts/check-codex-workflow.sh` |
| Terraform | `validations/terraform.sh` |
| Helm | `validations/helm.sh` |
| Kubernetes manifests | `validations/kubernetes.sh` |
| IAM / policy JSON | `validations/iam.sh` |
| 多類型變更 | `validations/all.sh` |

若工具未安裝或 repo 沒有對應檔案，要明確回報「未執行原因」，不可假裝已驗證。

## Git 慣例

- commit message 不加 `Co-Authored-By` 等協作者資訊。
- 不 revert 使用者或其他工具的既有變更，除非使用者明確要求。
- Commit 前執行與變更相關的 validation，並回報實際結果。
