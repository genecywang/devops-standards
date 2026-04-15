# Self-Service Ops Copilot Backlog

## 目標

以 `OpenClaw` 提供開發者自服務能力，優先處理高頻、低風險、可模板化的 DevOps 請求，對應 `KR1`。

## 第一版範圍

- 查 pod status
- 查 deployment rollout status
- 查最近 logs
- 查常見 metrics
- 查環境狀態

第一版不做 production write action。

## 第二版範圍

- non-production 限定 write actions
- restart test env
- rollout restart
- 其他低風險、可回滾操作

## Phase 0：互動模型

- [ ] 定義 Slack mention / thread interaction model
- [ ] 定義 request intent categories
- [ ] 定義 user identity / permission mapping
- [ ] 定義 confirmation / approval model
- [ ] 定義 response format

## Phase 1：Read Ops MVP

- [ ] `get_pod_status`
- [ ] `get_deployment_status`
- [ ] `get_recent_logs`
- [ ] `query_prometheus`
- [ ] `get_environment_summary`
- [ ] 定義 read ops prompt / response contract
- [ ] 定義常見問題範圍與拒答策略

## Phase 2：Permission 與安全邊界

- [ ] 限制使用環境為 `staging / test`
- [ ] 限制 namespace allowlist
- [ ] 限制 logs tail / query duration 上限
- [ ] 建立 user-level audit trail
- [ ] 建立 denied action logging

## Phase 3：Non-Production Write Actions

- [ ] 定義 write action allowlist
- [ ] 定義 restart test env contract
- [ ] 定義 rollout restart contract
- [ ] 定義 approval / confirmation step
- [ ] 定義 rollback guidance
- [ ] 將 write action 與 production 完全隔離

## Phase 4：衡量指標

- [ ] 每週私訊請求數 baseline
- [ ] self-service request volume
- [ ] self-service success rate
- [ ] first response time
- [ ] fallback to human handoff rate
- [ ] denied action rate

## 驗收標準

- staging / test 可穩定完成 read ops 查詢
- user interaction 與 tool usage 皆可審計
- non-production write actions 需明確 approval 才能執行
- 可量測對人工私訊請求的替代效果
