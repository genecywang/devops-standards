# AWS Alarm Coverage Expansion And ElastiCache Phase 1 Design

## Goal

在既有 `alert_auto_investigator` Phase 1 基礎上，新增一段仍然
**bounded、deterministic、read-only、fail-open** 的 AWS 擴充工作：

- 擴大真實 CloudWatch alarm shape 的分類覆蓋
- 補齊對應 golden replay coverage
- 將 `elasticache_cluster` 從 `SKIP` 提升為真正可調用的 investigation type

這一輪的目標不是把 AWS 告警全域做完，而是讓目前 production inventory 中
高頻、邊界清楚的 ElastiCache 告警正式進入 Phase 1 investigation plane。

---

## Why This Phase Exists

目前 AWS 路線已經完成：

- `rds_instance`
- `load_balancer`
- `target_group`

這幾個 bounded investigator 已經證明 Phase 1 的方向是可行的，但目前實際 alarm
inventory 顯示，`AWS/ElastiCache` 也是高頻來源，且仍停留在 parser 有辨識、
dispatcher / tool 無實作的狀態。

如果直接跳到更複雜的 `msk_cluster` 或 AI assist，會過早把系統帶離目前已經建立的
deterministic investigation 邊界。

因此下一步應該是：

1. 先把真實 AWS alarm surface 的分類覆蓋補齊
2. 用 golden replay 固定住 parser 與 routing 行為
3. 再實作下一個 bounded investigator：`elasticache_cluster`

---

## Scope

### In Scope

- CloudWatch dimension -> `resource_type` 規則補強，特別是
  `CacheClusterId` / `CacheNodeId`
- `elasticache_cluster` support posture 從 `SKIP` 提升到 `INVESTIGATE`
- `elasticache_cluster` 的 read-only AWS investigation tool
- 對應 dispatcher routing
- deterministic formatter output
- golden replay fixture 與 regression coverage
- support / operations / inventory 文件對齊

### Out Of Scope

- `msk_cluster` investigation
- ElastiCache root cause analysis
- CloudWatch metric graph correlation
- Redis / Valkey command 層級診斷
- cross-service correlation
- AI assist / reasoning layer
- write action
- 對現有 metadata contract 的擴張

---

## Boundary

這一輪仍屬於 `Phase 1 — Investigation Maturity`，不是 `Phase 2`。

必須維持以下邊界：

- investigation routing 仍由 deterministic dispatcher 決定
- Slack reply 仍由固定 formatter 產生
- tool 只回 bounded AWS facts
- 失敗時必須 fail-open，不得破壞既有 handler reply flow

這一輪不得演變成：

- 通用 AWS diagnostics agent
- 對 metric / topology 做自由推論
- 動態文字生成層
- CloudWatch history / trends 的多步分析

---

## Problem Statement

根據目前 repo 內的 inventory：

- `AWS/ElastiCache` alarm 數量高
- 常見 dimension shape 已包含：
  - `CacheClusterId`
  - `CacheClusterId + CacheNodeId`

但系統現況仍有 3 個缺口：

1. parser 與 support posture 雖已辨識 `CacheClusterId`，但 runtime policy 仍是
   `SKIP`
2. golden replay 尚未固定住真實 ElastiCache alarm shape
3. 沒有對應的 bounded investigator 可回答目前資源狀態

結果是：

- 真實 AWS 告警有分類，但沒有 investigation value
- 未來擴張 AWS coverage 時，缺少 fixture-based 回歸保護

---

## Approaches

### 1. Inventory-first + bounded ElastiCache investigator

先補分類、support matrix、golden replay，再加入
`get_elasticache_cluster_status`。

優點：

- 與目前 inventory 驅動的路線一致
- parser / dispatcher / tool / docs 可以同一輪收斂
- 最符合 Phase 1 的 deterministic 原則

缺點：

- 改動面比單純加一個 tool 略大

### 2. Tool-first ElastiCache

先做 tool，之後再回頭補 mapping 與 golden replay。

優點：

- 最快看到新 investigator

缺點：

- parser / support posture 仍然分裂
- 後續一定會補文件與 fixture 債
- 容易讓 implementation 先於 policy

### 3. Coverage-first only

只補 mapping 與 golden replay，不新增 investigator。

優點：

- 最保守
- 幾乎沒有 runtime 風險

缺點：

- 對真實值班價值提升有限
- Phase 1 investigation maturity 前進太少

---

## Recommendation

採用 `Inventory-first + bounded ElastiCache investigator`。

原因：

- 它同時處理 policy、classification、coverage、investigation value
- `elasticache_cluster` 比 `msk_cluster` 更適合作為下一個 bounded AWS tool
- 這條路線能延續目前 `rds_instance` / `load_balancer` /
  `target_group` 的工程邏輯，而不是另開一套例外流程

---

## Proposed Flow

1. CloudWatch alarm 進入 `cloudwatch_alarm` normalizer。
2. 若 dimensions 含有 `CacheClusterId` 或 `CacheNodeId` 關聯 shape，
   normalize 成 `resource_type=elasticache_cluster`。
3. control pipeline 依既有 policy 判定該 alert 可 investigation。
4. dispatcher 將事件路由到 `get_elasticache_cluster_status`。
5. tool 以 read-only AWS API 取得 bounded cluster / node facts。
6. formatter 產生固定 reply 與穩定 metadata。
7. 若 AWS API 失敗或資源不存在，回傳 deterministic failure / gone style 結果，
   不讓整個 handler 崩潰。

---

## Classification Design

### Resource Type Mapping

這一輪不追求更聰明的 parser，而是追求更明確的真實 alarm shape 支撐。

最低要求：

- `CacheClusterId` -> `elasticache_cluster`
- `CacheNodeId` 單獨出現時，不直接映射成新 resource type
- `CacheClusterId + CacheNodeId` 仍歸類為 `elasticache_cluster`

理由：

- 目前 investigation plane 還沒有 `elasticache_node` 這種獨立 resource boundary
- node-level 告警仍可先回到 cluster-bounded investigator，避免 resource taxonomy
  過早膨脹

### Resource Name Rule

`resource_name` 維持使用 `CacheClusterId` 的值。

即使 alarm 包含 `CacheNodeId`，第一版 investigation target 仍然是 cluster identity，
不以 node identity 作為 dispatcher target key。

### Support Matrix Rule

`elasticache_cluster` 從 `SKIP` 提升為 `INVESTIGATE`。

其餘 AWS resource posture 不因本輪而變動：

- `msk_cluster` 保持 `SKIP`
- `sqs_queue` 保持 `SKIP`
- `waf_web_acl` 保持 `SKIP`

---

## Investigation Design

### Tool Shape

在 `openclaw_foundation` 新增：

- `get_elasticache_cluster_status`

這個 tool 必須與現有 AWS tools 同樣遵守：

- read-only AWS API
- bounded output
- stable canonical response
- no free-form exploration

### Allowed AWS Evidence

第一版只允許使用 bounded、read-only、resource-scoped API facts。

可接受來源：

- `DescribeCacheClusters`
- 必要時包含 node info 與 engine / status / failover-related bounded fields

第一版不使用：

- CloudWatch metric lookup
- Events / logs
- 跨資源關聯 API
- parameter group / replication group 深度展開

### Minimum Output Facts

第一版 evidence 至少應能表達：

- `cache_cluster_id`
- `engine`
- `engine_version` 或可安全取得的最小版本欄位
- `cache_cluster_status`
- `num_cache_nodes`
- 每個 node 的最小 bounded status 摘要
- 是否有 operator attention signal

若 AWS API 已能穩定提供，也可加入：

- `replication_group_id`
- `preferred_availability_zone`
- `transit_encryption_enabled` 這類穩定布林欄位

但第一版不應為了欄位豐富度而擴張 API surface。

### Health Classification

第一版維持保守分類。

建議規則：

- cluster 存在且狀態穩定時：
  - `health_state=healthy`
  - `attention_required=false`
- cluster 存在但處於明顯非穩定狀態時：
  - `health_state=degraded` 或 `in_progress`
  - `attention_required=true`
- cluster 不存在時：
  - `health_state=gone`
  - `resource_exists=false`

`primary_reason` 必須來自固定規則，例如：

- `available`
- `modifying`
- `creating`
- `deleting`
- `cache_cluster_not_found`

不得由告警名稱或自由文字推論。

### Node-Level Alarm Handling

第一版不新增 `elasticache_node` investigator。

若 alarm 帶有 `CacheNodeId`，tool 可以在 bounded evidence 中附帶 node status，
但最終 summary 仍以 cluster-level 結論為主。

原因：

- 可保留 node signal 的操作價值
- 不需要在本輪引入新的 resource taxonomy、formatter 分支、support posture

### Formatter Rule

formatter 保持 deterministic、簡潔、固定格式。

第一版 summary 應偏向：

- healthy:
  - `ElastiCache cluster <id> is healthy`
- degraded:
  - `ElastiCache cluster <id> is degraded: status=modifying`
- gone:
  - `ElastiCache cluster <id> no longer exists`

如需顯示少量補充事實，可維持與現有 AWS investigation 相同風格，附加固定欄位，
但不得引入冗長敘述。

---

## Failure Behavior

此功能必須 fail-open。

允許的失敗結果：

- AWS API timeout / transient error
- cluster not found
- 部分 node info 缺失

約束：

- 不得讓 handler thread reply flow 中斷
- 不得因為單一欄位缺失就把整個 result 當成崩潰
- 不得改變其他 AWS resource investigation 行為

若 tool 無法取得完整資料，應優先：

1. 保留最小可證實 facts
2. 用固定 metadata 表達不完整狀態
3. 避免把不確定性包裝成精確 diagnosis

---

## Golden Replay Strategy

這一輪必須把真實 AWS coverage 的回歸保護補上。

最低 coverage：

1. `CacheClusterId` 的 CloudWatch alarm 可正確 normalize
2. `CacheClusterId + CacheNodeId` 的 CloudWatch alarm 仍 normalize 成
   `elasticache_cluster`
3. `elasticache_cluster` alert 會被 dispatcher 路由到
   `get_elasticache_cluster_status`
4. unsupported AWS resource type 既有 skip behavior 不退化
5. 至少一條 ElastiCache golden replay 能跑完整 parser -> dispatcher ->
   formatter path

這裡的目的是固定住真實 inventory shape，不是把所有 AWS 類型一次 golden 化。

---

## Implementation Shape

### `alert_auto_investigator`

應新增或調整：

- `normalizers/cloudwatch_alarm.py`
- `models/resource_type.py`
- `investigation/dispatcher.py`
- formatter / handler 測試
- golden replay 測試與 fixtures
- support / inventory 文件

### `openclaw_foundation`

應新增：

- ElastiCache read-only adapter methods
- fake provider fixture
- `get_elasticache_cluster_status` tool
- canonical response shaping tests

`openclaw_foundation` 仍只負責 AWS facts，不處理 bot-specific formatting policy。

---

## Permissions

### AWS IAM

第一版預期至少需要：

- `elasticache:DescribeCacheClusters`

若實作證明需要額外 read-only API 才能取得穩定 bounded facts，再補文件與最小 IAM，
但不得先擴權再找用途。

### Kubernetes / Helm

本輪不需要新增 Kubernetes RBAC。

原因：

- 這一輪是純 AWS read-only investigation
- 不涉及 cluster-side enrichment

---

## Logging

建議補以下低噪音事件：

- `dispatch_started resource_type=elasticache_cluster`
- `elasticache_cluster_lookup_started`
- `elasticache_cluster_lookup_not_found`
- `elasticache_cluster_lookup_failed`
- `elasticache_cluster_lookup_succeeded`

目的：

- 讓 runtime 驗證可觀測
- 不把 log 做成另一種 formatter output

---

## Testing

最低要求：

1. `CacheClusterId` alarm normalize 成 `elasticache_cluster`
2. `CacheClusterId + CacheNodeId` alarm 仍以 cluster identity investigate
3. dispatcher 能正確路由 `elasticache_cluster`
4. healthy cluster 產生 deterministic success summary 與 metadata
5. degraded cluster 產生 deterministic degraded summary 與 metadata
6. not found 產生 deterministic gone / missing result
7. AWS API failure 不會讓 handler flow 崩潰
8. 既有 `rds_instance` / `load_balancer` / `target_group` regression 不退化
9. golden replay 至少包含一條真實 ElastiCache alarm shape

測試層次應包含：

- unit tests for normalizer
- unit tests for ElastiCache adapter / tool
- dispatcher routing tests
- handler / formatter tests
- replay-based regression tests

---

## Rollout Plan

這一輪不需要像 `target_group` enrichment 那樣做 shadow output path，因為它是新的
primary investigation type，不是附加 enrichment。

但仍需要保守 rollout：

1. 先在測試與 fixture 層固定行為
2. 在非 production 環境驗證代表性 alarm
3. 再讓 production runtime 吃到新的 routing

runtime 驗證重點：

- 真實 ElastiCache alarm 是否成功 dispatch
- summary 是否簡潔且可操作
- 是否有明顯錯誤分類或誤判 healthy / degraded

---

## Acceptance Criteria

此 Phase 完成的條件：

- `elasticache_cluster` 被明確定義為 `INVESTIGATE`
- 真實 ElastiCache CloudWatch alarm shape 能穩定 normalize 與 dispatch
- `get_elasticache_cluster_status` 可回 bounded、可重複的 investigation 結果
- Slack reply 保持 deterministic
- AWS API failure 不會中斷既有 investigation flow
- golden replay 為 ElastiCache alarm shape 提供回歸保護

---

## Trade-Offs

### Benefits

- 把真實高頻 AWS alarm surface 正式納入 Phase 1 investigation plane
- 持續強化 deterministic coverage，而不是過早導入 AI assist
- 為後續 AWS 擴張建立更好的 inventory-first working model

### Costs

- 需要同時修改 parser、dispatcher、tool、tests、docs
- 第一版只能回答 bounded current state，不能回答 deeper root cause
- node-level ElastiCache alarms 仍會被 cluster-bounded summary 吸收

這個 trade-off 是合理的，因為本輪的重點是可控、可驗證、可回歸，而不是一次做深。

---

## Follow-On Work

如果這一輪證明有值，後續才考慮：

- `msk_cluster` bounded investigation
- 更完整的 AWS golden replay inventory
- ElastiCache replication group 級別的更細建模
- Phase 2 的 OpenClaw read-only assist

這些都不屬於本輪範圍。
