# AI Platform Roadmap

## 背景

目前 DevOps / Platform 工作中，存在大量可重複、可模板化、可交由 AI 輔助的工作，包括：

- 開發者私訊請求查 log / 查 pod 狀態
- 測試環境常見操作
- production 告警發生後的初步蒐證與診斷

方向不是做一個單純聊天 bot，而是將這些能力平台化，讓 `OpenClaw` 成為受控的 investigation / self-service engine。

## Objective

建立 AI 驅動的 DevOps 平台能力，優先將重複性維運工作自動化，提升團隊人效與 incident triage 速度。

## Key Results

### KR1：釋放人力

在 `staging / test` 先提供 `OpenClaw` self-service 能力，涵蓋：

- log 查詢
- pod 狀態查詢
- deployment / rollout 狀態查詢
- 常見 metrics 查詢
- 測試環境重啟

目標：

- 90 天內將此類開發者私訊請求減少 60%
- 常見請求的首次回覆時間降低 80%

備註：

- 若 adoption 高、流程穩定，再逐步朝 80% 私訊減量推進
- write action 僅限 non-production，且需獨立權限控制

### KR2：縮短 Triage / MTTR

讓 production 的高價值 infra alerts 優先由 `OpenClaw` 進行初步診斷，包括：

- CloudWatch Alarm
- Alertmanager
- node / pod / RDS 類高價值告警

目標：

- 讓 80% 的高價值 infra alerts 經過 `OpenClaw` 初步診斷
- 平均 triage time 降低 30%
- 需要人工手動蒐證的告警比例降低 70%

備註：

- `MTTR -40%` 可視為第二階段目標，不建議在第一版承諾
- 第一版主要改善 discovery、evidence gathering、初步 diagnosis

### KR3：平台化與可審計

建立可審計、可 rollout、可分環境控權的 AI 平台基礎能力。

目標：

- 所有 `OpenClaw` tool 使用都有 audit trail
- 生產環境維持 read-only investigation boundary
- staging / test 可受控開放有限 write action
- 建立 shadow mode 與逐步 rollout 機制

## 產品線切分

## 1. Self-Service Ops Copilot

對象：

- 開發者
- 測試 / 整合環境操作需求

典型能力：

- 查 pod status
- 查 deployment rollout
- 查最近 log
- 查 Prometheus metrics
- 查環境狀態
- 受控執行測試環境 restart

互動模式：

- Slack mention / thread follow-up
- 偏互動式 bot

價值：

- 降低 DevOps 被動支援負擔
- 讓開發者自行完成常見查詢與低風險操作

## 2. Alert Auto-Investigator

對象：

- on-call
- production incident triage

典型能力：

- 告警自動 intake
- 告警正規化
- deterministic control plane
- `OpenClaw` 自動調查
- Slack thread 回 evidence、likely cause、next step

互動模式：

- 第一版以單次事件自動回覆為主
- 第二版才考慮 thread follow-up

價值：

- 降低人工初步蒐證成本
- 縮短告警到初步判斷的時間

## 執行原則

- 不把所有能力混成一個大 bot
- read-only investigation 與 write action 分開治理
- production 與 non-production 使用不同安全策略
- 先做高頻、高價值、低風險場景
- 先證明 adoption 與節省人力，再擴權與擴範圍

## 分階段策略

### Phase 1：Alert Auto-Investigator MVP

- source 只支援 `CloudWatch Alarm` 與 `Alertmanager`
- 先做 normalized event + control plane
- `OpenClaw` 僅做 read-only investigation
- 回 Slack thread 固定格式結果
- 先在 shadow mode 驗證品質與成本

### Phase 2：Self-Service Read Ops

- 開放查 log / 查 pod / 查 deployment / 查 metrics
- 對象以 `staging / test` 為主
- 建立 Slack 互動模式與 audit trail

### Phase 3：Limited Write Actions In Non-Production

- 僅在 `staging / test` 開放有限 write actions
- 例如 rollout restart、重啟測試環境
- 需獨立權限、明確審批與完整 audit

### Phase 4：Expand Coverage

- 擴更多 alert 類型
- 擴更多 self-service runbooks
- 視 adoption 與風險，再考慮更深的 production 協作能力

## 衡量指標

### Self-Service

- 每週私訊請求數
- 自服務成功率
- 首次回覆時間
- 常見請求覆蓋率

### Alert Investigation

- investigate 覆蓋率
- triage time
- 人工蒐證比例
- investigation success rate
- 調查結果人工抽樣正確率

### 平台運營

- token / cost
- P95 latency
- tool timeout rate
- fallback rate
- policy deny rate

## 風險與原則

- 不高估第一版對 `MTTR` 的直接改善幅度
- 不在 production 一開始開 write action
- 不將 control plane 交給 LLM
- 不用聊天體驗掩蓋缺乏 evidence 的問題

## 下一步

- 先完成 `NormalizedAlertEvent v1`
- 先完成 `OpenClaw security boundary`
- 完成 `Platform Foundation` backlog
- 完成 `Alert Auto-Investigator` backlog
- 完成 `Self-Service Ops Copilot` backlog
