# Self-Service Ops Copilot — Slack MVP Design

**Date:** 2026-04-13
**Status:** Approved (rev 2 — foundation alignment fixes)
**Scope:** Phase 1 MVP — Slack Socket Mode bot, @mention + semi-structured grammar, read-only tool dispatch via OpenClawRunner

---

## 目標

讓開發者透過 Slack @mention 查詢 Kubernetes 資源狀態，入口走 Slack，execution 走 `openclaw_foundation` 的 `OpenClawRunner` + `ToolRegistry`，共用同一套 foundation boundary。

## Non-Goals

- NLP / 自然語言解析
- Slash command（避免額外 Slack app 設定）
- Slack rich blocks / Block Kit（MVP 先用 plain text）
- write actions（Phase 1 僅 read-only）
- production 環境 cluster（MVP 以 staging 為主）
- Slack integration 自動化測試

---

## Foundation Model 變更（這輪需要，最小化）

### `InvestigationRequest` 新增 `requested_by`

```python
@dataclass(slots=True)
class InvestigationRequest:
    ...
    requested_by: str | None = None   # 新增 optional field
```

Backward compatible（optional，None default），現有 CLI tests 不需更動。Dispatcher 從 `SlackContext.actor_id` 填入，供 audit 使用。

### `CanonicalResponse` 這輪不動

Formatter 這輪只使用 `summary + result_state`，不需要 `evidence`。`CanonicalResponse` 加 `evidence` 欄位 defer 到下一輪（需同時修改 runner 傳遞 `tool_result.evidence`）。

### Runner `result_state` 這輪的真實範圍

Runner 這輪實際會回的 `result_state`：`SUCCESS`、`FAILED`、`FALLBACK`。`DENIED` 和 `PARTIAL` 不由 runner 發出，`DENIED` 全留在 dispatcher（`DispatchError`，runner 不介入），`PARTIAL` defer。

---

## Package 結構

`openclaw_foundation` 除加入 `requested_by` optional field 外維持不變。Slack bot 與 Copilot product logic 獨立放在 `self_service_copilot/` package。

```
self_service_copilot/
├── pyproject.toml
├── src/
│   └── self_service_copilot/
│       ├── __init__.py
│       ├── bot.py          # Slack Socket Mode app + mention handler
│       ├── config.py       # CopilotConfig dataclass
│       ├── parser.py       # mention text → ParsedCommand
│       ├── dispatcher.py   # ParsedCommand + SlackContext → InvestigationRequest
│       └── formatter.py    # CanonicalResponse / ParseError / DispatchError → Slack reply string
└── tests/
    ├── test_parser.py
    ├── test_dispatcher.py
    └── test_formatter.py
```

---

## Control Flow

```
Slack @mention event
    ↓
bot.py: SocketModeHandler receives app_mention event
    ↓
parser.parse(text, bot_user_id, supported_tools) → ParsedCommand
    ↓ (ParseError → format_parse_error → say(thread_ts) → return)
dispatcher.build_request(cmd, ctx, config) → InvestigationRequest
    ↓ (DispatchError → format_dispatch_error → say(thread_ts) → return)
OpenClawRunner(registry).run(request) → CanonicalResponse
    ↓
formatter.format_response(response, cmd) → str
    ↓
say(reply_str, thread_ts=event_ts)
```

`bot.py` 在 process 啟動時初始化 `ToolRegistry`（register `KubernetesPodStatusTool`、`KubernetesPodEventsTool`），接著 `SocketModeHandler.start()` 進 blocking loop。全部跑在同一個 sync process，不引入 queue 或 async worker。

Provider wiring（fake vs real）由 `CopilotConfig` 控制，不寫死在 `bot.py`。

---

## Command Grammar

```
@copilot <tool_name> <namespace> <resource_name>
```

MVP 支援 tool_name：

| tool_name | 語意 |
|---|---|
| `get_pod_status` | 查 pod 狀態 |
| `get_pod_events` | 查 pod events |

`resource_name` 在目前兩個 tool 對應 pod name。grammar 使用 `resource_name` 而非 `pod_name`，避免之後加 `get_deployment_status` 時需要重命名 model。

`SUPPORTED_TOOLS` 的唯一來源是 `CopilotConfig.supported_tools`，parser 引用 config 傳入的集合，不自己維護副本。

---

## Parser Contract

**`ParsedCommand`（frozen dataclass）：**

```python
@dataclass(frozen=True)
class ParsedCommand:
    tool_name: str
    namespace: str
    resource_name: str
    raw_text: str     # 原始 mention 文字，供 audit / debug 用
```

**`ParseError` 分兩種：**

```python
class ParseError(ValueError):
    pass

class UnknownCommandError(ParseError):
    pass   # tool_name 不在 supported_tools

class UsageError(ParseError):
    pass   # argument 數量錯誤
```

**`parse(text, bot_user_id, supported_tools)` 行為：**

1. 移除 `<@BOT_USER_ID>`，strip 前後空白
2. 以空白 split，容忍多餘空白（先 strip() 再 split()）
3. 預期恰好 3 個 token（tool_name、namespace、resource_name）
4. token 數不對 → `UsageError`
5. tool_name 不在 `supported_tools` → `UnknownCommandError`
6. 通過 → 回 `ParsedCommand`

**責任邊界：** `parser.py` 只處理 text，不碰 Slack event metadata（actor、channel、ts）。

---

## Dispatcher Contract

**`SlackContext`（frozen dataclass）：**

```python
@dataclass(frozen=True)
class SlackContext:
    actor_id: str     # Slack user ID
    channel_id: str
    event_ts: str     # thread reply 用，也當 request_id seed
```

**`DispatchError`：**

```python
class DispatchError(ValueError):
    pass   # allowlist violation — tool / namespace / cluster 不在允許範圍
```

**`build_request(cmd, ctx, config)` 補的 canonical defaults：**

| InvestigationRequest 欄位 | 來源 |
|---|---|
| `request_id` | `make_request_id(ctx)` — helper 封裝，不散落字串拼接 |
| `input_ref` | `f"slack://{ctx.channel_id}/{ctx.event_ts}"` — 穩定對應 Slack event，供 audit / trace 用 |
| `source_product` | `"self_service_copilot"` |
| `requested_by` | `ctx.actor_id` |
| `scope.cluster` | `config.cluster`（不從 user input 取）|
| `scope.environment` | `config.environment` |
| `budget` | `config.default_budget`（user 不可控制）|
| `target.cluster` | `config.cluster` |
| `target.namespace` | `cmd.namespace` |
| `target.resource_name` | `cmd.resource_name` |
| `tool_name` | `cmd.tool_name` |

**Dispatcher 的四個責任：**

1. canonical field mapping
2. config-driven default injection
3. input boundary check（第一層 product-side policy gate）：
   - `cmd.tool_name` 不在 `config.supported_tools` → `DispatchError`
   - `cmd.namespace` 不在 `config.allowed_namespaces` → `DispatchError`
   - `config.cluster` 不在 `config.allowed_clusters` → `DispatchError`
4. request identity construction via `make_request_id(ctx)`

`cluster` 永遠從 config 來，使用者無法透過 mention 影響 cluster scope。

---

## CopilotConfig

```python
@dataclass
class CopilotConfig:
    cluster: str
    environment: str
    allowed_clusters: set[str]
    allowed_namespaces: set[str]
    supported_tools: frozenset[str]    # SUPPORTED_TOOLS 唯一來源
    default_budget: ExecutionBudget
    provider: str                      # "fake" | "real"
```

從 env variables 讀取，`bot.py` 啟動時建立，傳入 dispatcher 與 bot。

---

## Formatter Contract

**原則：** plain text，thread-friendly，不做 Slack Block Kit。以 canonical `result_state` / error type 決定格式，不靠 message string 猜。Formatter 這輪只用 `CanonicalResponse.summary + result_state`，不依賴 `evidence`（`CanonicalResponse` 尚未有此欄位）。

**success（`result_state=SUCCESS`）：**

```
[success] get_pod_status payments/payments-api-123
pod payments-api-123 is Running
```

`summary` 由 tool 填入，formatter 直接使用，不自行 parse evidence。

**failed（`result_state=FAILED`）：**

```
[failed] get_pod_status payments/payments-api-123
no registered tool available for get_pod_status
```

**fallback（`result_state=FALLBACK`）：**

```
[fallback] get_pod_status payments/payments-api-123
budget exhausted before tool execution
```

**dispatcher deny（`DispatchError`，不進 runner）：**

```
[denied] namespace "internal" is not allowed
```

**user error（`ParseError`）：**

```
[unknown command] get_pod_statuss
Supported: get_pod_events <namespace> <resource_name>, get_pod_status <namespace> <resource_name>

[usage] get_pod_status requires: <namespace> <resource_name>
```

`supported_tools` 顯示時固定排序（sorted），確保輸出穩定。

**Formatter 介面：**

```python
def format_response(response: CanonicalResponse, cmd: ParsedCommand) -> str: ...
def format_parse_error(error: ParseError, supported_tools: frozenset[str]) -> str: ...
def format_dispatch_error(error: DispatchError, cmd: ParsedCommand) -> str: ...
```

---

## Error Handling

**bot.py handler 內的處理層次：**

```
ParseError (UnknownCommandError / UsageError)
    → format_parse_error → say(thread_ts)
    → return

DispatchError (allowlist violation)
    → format_dispatch_error → say(thread_ts)
    → return

runner result_state = SUCCESS / FAILED / FALLBACK
    → format_response → say(thread_ts)

Unhandled exception（catch-all）
    → log full traceback
    → say("[error] unexpected failure, please retry", thread_ts)
    → return

Slack SDK error on say()
    → log only，MVP 不重試
```

---

## Testing Scope

`parser / dispatcher / formatter` 三層全部 pure function，可直接單元測試。`bot.py` 不做單元測試（需 mock Slack SDK，MVP 跳過）。

| 測試檔 | 覆蓋範圍 |
|---|---|
| `test_parser.py` | valid 輸入、`UnknownCommandError`、`UsageError`、多餘空白 strip |
| `test_dispatcher.py` | 欄位映射（含 `requested_by`）、cluster 永遠從 config 來、allowlist deny、`request_id` 格式 |
| `test_formatter.py` | `SUCCESS` / `FAILED` / `FALLBACK`、`ParseError` 兩種、`DispatchError`、`supported_tools` 排序穩定 |

---

## MVP 限制

- 只支援 `get_pod_status` 和 `get_pod_events`
- 只支援 staging cluster（production 不在 MVP 範圍）
- Formatter 只用 `summary + result_state`，不讀 `evidence`（下一輪再擴充）
- Runner 只處理 `SUCCESS` / `FAILED` / `FALLBACK`，`DENIED` 在 dispatcher 攔截，`PARTIAL` defer
- 不做 dedup / rate limit / cooldown（Phase 2）
- 不做 user permission mapping（Phase 2）
- 不做 rich blocks（後續視需要加）
- Slack SDK error 不重試

---

## 後續演進項目

- 加入 `get_deployment_status`、`get_recent_logs`、`query_prometheus`（grammar 不需改，register 新 tool 即可）
- `CanonicalResponse` 加 `evidence` 欄位，formatter 輸出更豐富的結構化內容
- user permission / namespace 存取控制（依 Slack user ID 限制可查 namespace）
- dedup / rate limit（同一使用者短時間大量查詢）
- async worker（多 pod 水平擴展時）
- Slack Block Kit 格式化（改善可讀性）
- production cluster 上線（先 shadow mode 觀察）
