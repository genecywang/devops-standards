# Platform Foundation Backlog

## 目標

建立 `OpenClaw` 驅動的 AI 平台共用底座，供以下兩條產品線共用：

- `Alert Auto-Investigator`
- `Self-Service Ops Copilot`

## 實作文件對應

- `docs/platform-foundation/contracts.md`
- `docs/platform-foundation/runtime.md`
- `docs/platform-foundation/tool-layer.md`
- `docs/platform-foundation/security.md`
- `docs/platform-foundation/observability.md`
- `docs/platform-foundation/rollout.md`

## 驗收標準

- 共用 tool layer 可同時支援 alert 與 self-service
- 所有 tool 均可審計
- read-only 邊界在 production 可強制執行
- fallback、timeout、redaction 行為可預測
