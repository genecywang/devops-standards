# OpenClaw Foundation Skeleton Design

## Objective

在這個 repo 內新增一個專屬的 Python package 目錄，實作 `OpenClaw foundation` 的最小可執行 skeleton，先把 `contracts + runtime` 跑成一條本機可執行 flow。

這個 skeleton 的目的不是直接接真實 AWS / Kubernetes / Slack，而是先固定 package 邊界、資料模型、runtime 控制流與 fake tool integration，讓後續擴充 provider adapter 與 security / tool layer 時不需要重拆主體。

## Scope

第一版只包含下列能力：

- Python package 結構，可被本 repo 直接執行與測試
- canonical request / response / budget models
- minimal `openclaw_runner`
- runtime state transition
- tool base interface 與 registry
- 一個 fake tool
- fixture 驅動的最小執行 flow
- 基本測試

## Non-Goals

這一版不做：

- 真實 AWS / Kubernetes / Prometheus client
- 真 Slack ingress / responder
- 真 audit sink 或 metrics backend
- 真 IRSA / RBAC / NetworkPolicy implementation
- production-ready config loading
- multi-tool orchestration

## Proposed Layout

建議新增目錄：

```text
openclaw_foundation/
  pyproject.toml
  README.md
  src/openclaw_foundation/
    __init__.py
    cli.py
    models/
      __init__.py
      enums.py
      requests.py
      responses.py
    runtime/
      __init__.py
      runner.py
      state_machine.py
    tools/
      __init__.py
      base.py
      registry.py
      fake_investigation.py
    fixtures/
      investigation_request.json
  tests/
    test_models.py
    test_runner.py
    test_cli.py
```

## Core Flow

最小 flow 如下：

1. CLI 載入 fixture request
2. request model 做 schema validation
3. runner 建立 runtime context，進入 `received -> validated -> executing`
4. runner 從 registry 找到 fake tool
5. fake tool 回傳固定 evidence
6. runner 做最小 redaction pass
7. state transition 到 `completed`
8. 輸出 canonical response，`result_state=success`

失敗路徑至少包含：

- schema invalid -> `result_state=denied`
- tool not found -> `result_state=failed`
- budget exceeded -> `result_state=fallback`

## Design Decisions

### 1. Package First

這次直接做成正式 Python package，而不是零散 script。

原因：

- 後面 `contracts`、`runtime`、`tool layer` 的邊界會比較穩
- 測試與 CLI entrypoint 比較容易維護
- 後續擴充 provider adapter 時，不需要先重構檔案結構

### 2. Contracts and Runtime First

第一版只做 `contracts + runtime` 最小閉環。

原因：

- 先把 control plane 主體跑起來
- 之後 security 與 tool enforcement 可以掛在既有 runner / tool base 上
- 避免一開始把真實 provider 與安全邊界一起拉進來，scope 失控

### 3. Fake Tool Instead of Real Integrations

第一版只放一個 fake investigation tool。

原因：

- 驗證 runner / registry / response contract 是否正確即可
- 不讓外部 API、credential、network access 干擾基礎結構
- 後續真 tool 可以直接替換同一個 interface

## Interfaces

### Request Model

至少包含：

- `request_type`
- `request_id`
- `source_product`
- `scope`
- `budget`
- `input_ref`

### Response Model

至少包含：

- `request_id`
- `result_state`
- `summary`
- `actions_attempted`
- `redaction_applied`

### Tool Interface

至少包含：

- `tool_name`
- `supported_request_types`
- `invoke()`

### Runner Responsibilities

- validate request
- allocate budget
- resolve tool from registry
- track runtime state
- convert tool result into canonical response
- apply minimal redaction before output

## Testing

第一版至少要有：

- model validation test
- runner success path test
- runner failure path test
- CLI smoke test

## Acceptance Criteria

完成時應能：

- 在本 repo 內用單一命令執行最小 flow
- 印出 canonical response JSON
- 看得到 runtime state transition
- test 能覆蓋 success / denied / failed / fallback 基本路徑
- package 結構能支撐後續真 tool 與 security / tool layer 擴充

## Risks

- 若一開始把 provider adapter 一起拉進來，會使 skeleton 被外部依賴主導
- 若不先固定 response / runner 邊界，後面每接一個 tool 都會倒逼重構
- 若 CLI 與 tests 不先放進來，之後很難快速驗證 runtime 變更是否破壞 flow

## Implementation Handoff

下一步應先寫 implementation plan，再開始建 `openclaw_foundation/` package。
第一個 implementation milestone 應只處理：

- package scaffolding
- models
- runner
- fake tool
- CLI
- tests
