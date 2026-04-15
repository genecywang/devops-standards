# NormalizedAlertEvent v1

## 目的

`NormalizedAlertEvent` 是 investigator service 的內部 canonical event model。

目標：

- 將不同來源的告警轉成一致的 control fields
- 讓 control plane 可用 deterministic 規則處理
- 降低 `OpenClaw` 需要理解的來源差異
- 為 dedup、ownership、resolved handling、policy 提供穩定輸入

## 設計原則

- source-specific payload 必須在 ingress edge 轉換
- schema 優先服務 control plane，而不是追求完整保留所有來源細節
- 缺少必要欄位時，預設 `fail-close` 或 `summarize-only`
- schema 版本必須顯式標示

## 必填欄位

| 欄位 | 型別 | 說明 |
|---|---|---|
| `schema_version` | string | 固定為 `v1` |
| `source` | string | `cloudwatch_alarm` 或 `alertmanager` |
| `status` | string | `firing`、`resolved`、`unknown` |
| `environment` | string | 例如 `prod-jp`、`prod-au` |
| `region_code` | string | 例如 `ap-northeast-1` |
| `alert_name` | string | 告警名稱 |
| `alert_key` | string | dedup / cooldown 使用的穩定 key，不含 state |
| `resource_type` | string | 例如 `rds_instance`、`node`、`pod`、`deployment`、`unknown` |
| `resource_name` | string | 具體資源名稱 |
| `summary` | string | 短摘要，給人看 |
| `event_time` | string | 事件時間，建議 ISO 8601 |

## 建議欄位

| 欄位 | 型別 | 說明 |
|---|---|---|
| `account_id` | string | AWS account id |
| `cluster` | string | EKS cluster name |
| `severity` | string | `critical`、`warning` 等 |
| `namespace` | string | K8s namespace 或 CloudWatch namespace |
| `metric_name` | string | 指標名稱 |
| `description` | string | 補充描述 |
| `raw_text` | string | 原始 Slack 文字 |
| `raw_payload` | object | 原始來源 payload |

## JSON 範例

```json
{
  "schema_version": "v1",
  "source": "cloudwatch_alarm",
  "status": "firing",
  "environment": "prod-jp",
  "region_code": "ap-northeast-1",
  "account_id": "416885395773",
  "alert_name": "p-rds-shuriken_ReadIOPS",
  "alert_key": "cloudwatch_alarm:416885395773:ap-northeast-1:p-rds-shuriken_ReadIOPS",
  "resource_type": "rds_instance",
  "resource_name": "shuriken",
  "summary": "CloudWatch alarm triggered for RDS ReadIOPS",
  "event_time": "2026-04-12T13:05:43.360+0000",
  "namespace": "AWS/RDS",
  "metric_name": "ReadIOPS",
  "description": "Threshold Crossed: 4 out of the last 4 datapoints were greater than the threshold",
  "raw_payload": {}
}
```

## Control Plane 使用方式

### ownership

使用以下欄位判斷是否屬於本環境：

- `environment`
- `region_code`
- 必要時 `account_id`
- K8s 類事件可補 `cluster`

### dedup / cooldown

使用 `alert_key`。

要求：

- 同一資源同一類告警在 `firing` / `resolved` 間共用同一 key
- `alert_key` 不可包含 timestamp
- `alert_key` 不可包含容易抖動的非必要 labels

### resolved handling

使用 `status`。

規則：

- `resolved` 不進 investigate
- `unknown` 預設 `summarize-only` 或 skip

## Source Mapping

## CloudWatch Alarm

### mapping

| 原始欄位 | Normalized 欄位 |
|---|---|
| 固定值 | `source=cloudwatch_alarm` |
| `NewStateValue=ALARM` | `status=firing` |
| `NewStateValue=OK` | `status=resolved` |
| 其他 state | `status=unknown` |
| Lambda env `ALERT_ENV` | `environment` |
| `AlarmArn` region | `region_code` |
| `AWSAccountId` | `account_id` |
| `AlarmName` | `alert_name` |
| `StateChangeTime` | `event_time` |
| `Trigger.Namespace` | `namespace` |
| `Trigger.MetricName` | `metric_name` |
| `NewStateReason` | `description` |

### `alert_key`

格式：

```text
cloudwatch_alarm:{account_id}:{region_code}:{alert_name}
```

### `resource_type` / `resource_name`

由 `Trigger.Dimensions` 映射：

- `DBInstanceIdentifier` -> `rds_instance`
- `InstanceId` -> `ec2_instance`
- `LoadBalancer` -> `load_balancer`
- `ClusterName` -> `eks_cluster`
- 無法判定 -> `unknown`

## Alertmanager

### mapping

| 原始欄位 | Normalized 欄位 |
|---|---|
| 固定值 | `source=alertmanager` |
| alert status | `status` |
| template / config env | `environment` |
| label `region` 或 config | `region_code` |
| `labels.alertname` | `alert_name` |
| `annotations.summary` | `summary` |
| `annotations.description` | `description` |
| `labels.severity` | `severity` |
| `startsAt` / `endsAt` | `event_time` |
| `ClusterName` 或 config | `cluster` |

### `resource_type` / `resource_name`

優先順序：

- 有 `pod` -> `resource_type=pod`
- 有 `deployment` -> `resource_type=deployment`
- 有 `node` -> `resource_type=node`
- 有 `instance` 且屬於 node 類告警 -> `resource_type=node`
- 其他 -> `resource_type=unknown`

`resource_name` 取對應 label 值；若無，填 `unknown`。

### `alert_key`

建議規則：

- node 類：`alertmanager:{cluster}:{alert_name}:{resource_name}`
- pod 類：`alertmanager:{cluster}:{namespace}:{alert_name}:{resource_name}`
- deployment 類：`alertmanager:{cluster}:{namespace}:{alert_name}:{resource_name}`

## Slack Message Contract

Slack 訊息可分成兩段：

1. 給人看的摘要
2. 給機器 parse 的固定 metadata block

machine-readable block 必須包含：

- `schema_version`
- `source`
- `status`
- `environment`
- `region_code`
- `alert_name`
- `alert_key`
- `resource_type`
- `resource_name`
- `event_time`

## Versioning

- 第一版固定 `schema_version=v1`
- parser 對未知欄位採忽略策略
- parser 對缺少必填欄位採 `summarize-only` 或 skip
- 若未來有 breaking change，升版為 `v2`
- `v1` 與 `v2` 可在過渡期並行支援

## Fail-safe 規則

- `schema_version` 不支援 -> skip 或 summarize-only
- 缺少 `alert_key` -> 不進 investigate
- 缺少 `status` -> 視為 `unknown`
- 缺少 `environment` 或 `region_code` -> 不做 ownership-sensitive investigate

## 驗收標準

- CloudWatch Alarm 與 Alertmanager 都能映射到 `v1`
- resolved 不會誤進 investigate
- `alert_key` 對同一告警穩定
- parser 對未知欄位不會失敗
- 缺欄位時行為可預測
