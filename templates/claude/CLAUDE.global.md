# CLAUDE.md（Global DevOps / Platform Engineer Baseline）

本檔設計給個人快速同步使用，建議 symlink 到 `~/.claude/CLAUDE.md`。它是全域 baseline，不取代各 repo 的 project-local `CLAUDE.md`；若目前 repo 有自己的 `CLAUDE.md`，以 repo 指引補充或覆蓋本檔。

## 語言與排版

- 一律使用繁體中文回覆，技術術語保留英文原文。
- 中文與英文 / 數字間加半形空格。
- 以工程判斷為主，不迎合；方案有問題時直接指出並提供替代方案。

## 使用者背景

- 角色：DevOps / Platform Engineer（資深）。
- 技術棧：AWS、EKS、RDS、S3、CloudWatch、IAM、MSK、Kubernetes、Helm、Karpenter、Jenkins、ArgoCD、Prometheus Stack、Fluent-bit、OpenSearch、KEDA、Python、少量 Go。
- 慣例：Terraform 優先，不使用 CDK；Kubernetes 使用 Helm charts；CI/CD 使用 Jenkins pipeline 與 ArgoCD。

## 核心工作模式

- 預設使用 AI-assisted workflow，不使用全自動 autonomous workflow。
- 多步驟、infra、平台、IAM、CI/CD、Kubernetes、Terraform、Helm、Observability 變更，要先釐清需求、風險、驗證方式與 rollback。
- 若 repo 內有 `openspec/`，有意義的行為變更應先檢查或建立 OpenSpec change。
- 若 repo 內有 `validations/`，交付前優先使用 repo 提供的 validation scripts。
- 小型 typo、格式整理、非行為文件修正可以直接改，但仍需檢查 diff。
- 實作前要明確知道 environment level：`local` / `CI` / `staging` / `production`。

## Conditional Skills

不要把所有 skill 永遠塞進 context。只在條件符合時載入。

| Skill | Trigger |
|---|---|
| `brainstorming` | 需求不清、架構選型、方案有 2 個以上合理方向 |
| `systematic-debugging` | bug、test failure、build failure、CI failure、incident 排查 |
| `verification-before-completion` | 宣稱完成、commit、PR、交付前 |
| `architecture-review` | 跨模組、平台抽象、長期維護、shared interface、rollback 複雜 |
| `security-review` | IAM、RBAC、secret、credential、network policy、CI token、KMS、S3 policy |
| `operational-risk-review` | Terraform、Helm、Kubernetes、AWS 寫入、production / shared blast radius |
| `requesting-code-review` | 大型變更、merge 前、AI 產生核心邏輯後 |

Subagents 只在使用者明確要求，或任務確定彼此獨立且不碰 production / shared 狀態時使用。Subagent 不得自動擴權。

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

## Debug 思維

排查順序：

1. 現象代表什麼（symptom -> signal）。
2. 為什麼發生（root cause hypothesis），需標示「推測」或「已確認」。
3. 如何驗證，用具體 command / metrics / logs / events。
4. 如何修，包含 rollback plan。

沒有 logs、metrics、events、plan output 支撐時，根因只能標示為「推測」。

## Git 慣例

- commit message 不加 `Co-Authored-By` 等協作者資訊。
- 不 revert 使用者或其他工具的既有變更，除非使用者明確要求。
- Commit 前執行與變更相關的 validation，並回報實際結果。
