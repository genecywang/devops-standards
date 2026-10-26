# Codex Workflow Bootstrap Prompt

Use this prompt when checking or setting up this standards repository, not on every new session:

```text
Goal
檢查本 repo 的 Codex workflow setup，回報缺口並完成已授權的初始化。

Context
先執行 scripts/check-codex-workflow.sh，參考 README 的 bootstrap 與 personal sync 說明。
Superpowers 是選用套件，未安裝不代表 setup 失敗。

Constraints / Authorization
本機唯讀檢查可直接執行。全域套件安裝、personal sync 或替換既有設定，
須有使用者對該範圍的明確授權；先準備變更與影響，再詢問尚缺的授權。
已授權的同一操作不重複確認；不自動開啟 permission bypass。
保留既有 machine-local config，不存取 credentials 或操作 production/shared state。

Deliverable
列出實際缺口、需要的具體動作與驗證結果。
需 personal sync 時先使用 --dry-run；--force 僅用於已授權的替換。

Done when
必要 setup 已完成或未完成原因明確列出。
初始化後執行 setup check；若改動 scripts 或 sync 行為，執行對應測試。
Bootstrap 只建立缺少的本機 config 並檢查 setup，不安裝套件。
Infra validation 依實際變更類型執行，不為普通 session 或 setup 重跑完整測試。
```
