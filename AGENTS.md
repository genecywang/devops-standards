# AGENTS.md（devops-standards Repository）

本 repo 是 DevOps / Platform Engineering AI workflow standards 的 source of truth，用來追蹤與分發 Codex / Claude Code 規範、conditional skills、workflow playbooks 與 validation scripts。它不是一般 consumer project。

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

- 調整 agent 行為、workflow、approval gate、validation semantics 時，記錄意圖、影響與驗證方式；可使用對話、issue、PR 或必要的設計文件，不強制特定規格工具或文件組。
- 同步更新 Codex 與 Claude Code 相關模板，避免兩邊規範漂移。
- 保持 global templates 精簡；詳細流程放 `workflows/`，判斷型 checklist 放 `skills/`，可重跑檢查放 `validations/`。
- 不要把 machine-local config、secret、credential、personal token、absolute home path 寫入可提交檔案。
- `.codex/config.toml` 與 `.claude/settings.local.json` 是本機檔案，不進 git。

## 執行與 skills

- 已授權的本機修改、驗證與修正可連續完成，不為一般實作細節重複索取確認。
- 變更依 `workflows/ai-coding-workflow.md` 分級，規劃與紀錄深度對應風險；歷史資料不作為現行指令。
- Superpowers 是可選工具箱，不因開始對話載入 `using-superpowers`。Brainstorming 僅用於需求不明或重要設計取捨；TDD、review、驗證依風險與可測行為選用，不強制逐 task approval、重跑已有效的檢查或使用 subagents。
- 上述是對 skill guidelines 的明確使用者覆寫，不取代平台權限與下列操作邊界。Review readiness 不授權外部寫入。
- Execution environment 與 artifact 的 target environment 分開記錄；本機準備 production diff 不等於部署。

- 請依 global baseline 的成本分級委派可獨立且有實際效益的工作；不預設所有 subagents 繼承主模型。Codex 詳見 `workflows/model-skill-evaluation.md` 的 Subagent routing；Claude 使用 client 支援的對應模型，不照抄 Codex IDs。

## Personal Sync

個人快速同步使用：

```zsh
scripts/sync-personal-ai-config.sh
```

此腳本會建立：

- `~/.codex/AGENTS.md -> templates/codex/AGENTS.global.md`
- `~/.claude/CLAUDE.md -> templates/claude/CLAUDE.global.md`
- `~/.agents/skills/gene-devops-* -> skills/*`
- `~/.codex/standards/{workflows,prompts,validations}` 與 `~/.claude/standards/{workflows,prompts,validations}` 分別連結至本 repo 對應目錄

預設不覆蓋既有檔案；需要替換時使用 `--force`，腳本會先產生 `.bak.<timestamp>`。Skill 備份放在對應 client 的 `skill-backups/`，不留在預設 skills 掃描目錄。

## 變更流程

依任務需要釐清目標與範圍，完成已授權的實作、相關驗證與 review。
小任務可直接執行；有重要設計或營運風險時，補上必要的決策、影響與 rollback 紀錄。
不要求固定 proposal/specs/design/tasks 文件組或 archive 步驟。

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
| Shell scripts | `scripts/check-shell-syntax.sh` |
| Personal sync | `bash tests/sync-personal-ai-config.test.sh` |
| Workflow setup | `python3 -m unittest discover -s tests -p 'test_*.py'`、`scripts/check-codex-workflow.sh` |
| Terraform | `validations/terraform.sh` |
| Helm | `validations/helm.sh` |
| Kubernetes manifests | `validations/kubernetes.sh` |
| IAM / policy JSON | `validations/iam.sh` |
| 多類型變更 | `validations/all.sh` |

必要檢查通過後，僅在新變更、失敗或未解疑慮時擴大／重跑驗證。

若工具未安裝或 repo 沒有對應檔案，要明確回報「未執行原因」，不可假裝已驗證。

## Git 慣例

- commit message 不加 `Co-Authored-By` 等協作者資訊。
- 不 revert 使用者或其他工具的既有變更，除非使用者明確要求。
- Commit 前執行與變更相關的 validation，並回報實際結果。
