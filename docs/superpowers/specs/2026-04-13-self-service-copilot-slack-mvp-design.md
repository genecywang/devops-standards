# Self-Service Ops Copilot — Slack MVP Design

**Date:** 2026-04-13
**Status:** Approved
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

## Package 結構

`openclaw_foundation` 維持 runtime / tool / adapter 邊界不變。Slack bot 與 Copilot product logic 獨立放在 `self_service_copilot/` package。

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
│       └── formatter.py    # ToolResult / ParseError → Slack reply string
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
parser.parse(text, bot_user_id) → ParsedCommand
    ↓ (ParseError → format_parse_error → say → return)
dispatcher.build_request(cmd, ctx, config) → InvestigationRequest
    ↓ (DispatchError → format deny → say → return)
OpenClawRunner(registry).run(request) → CanonicalResponse
    ↓
formatter.format_tool_result(response, cmd) → str
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

**`build_request(cmd, ctx, config)` 補的 canonical defaults：**

| InvestigationRequest 欄位 | 來源 |
|---|---|
| `request_id` | `make_request_id(ctx)` — 封裝在 helper，不散落字串拼接 |
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

**原則：** plain text，thread-friendly，不做 Slack Block Kit。以 canonical `result_state` / error type 決定格式，不靠 message string 猜。

**success：**

```
[success] get_pod_status payments/payments-api-123
phase: Running
containers: app (ready), sidecar (ready)
node: node-a
```

**partial（budget exceeded 或單一 tool timeout）：**

```
[partial] get_pod_events payments/payments-api-123
partial result only
reason: budget exceeded
...evidence if any...
```

**user error：**

```
[unknown command] get_pod_statuss
Supported: get_pod_events <namespace> <resource_name>, get_pod_status <namespace> <resource_name>

[usage] get_pod_status requires 2 arguments: <namespace> <resource_name>
```

`supported_tools` 顯示時固定排序（sorted），確保輸出穩定。

**platform error（denied / failed / fallback）：**

```
[denied] namespace "internal" is not allowed

[failed] cluster endpoint unreachable
next check: verify DNS, network path, VPN, or cluster endpoint

[fallback] partial result only — investigation budget exceeded
```

**Formatter 介面：**

```python
def format_tool_result(response: CanonicalResponse, cmd: ParsedCommand) -> str: ...
def format_parse_error(error: ParseError, supported_tools: frozenset[str]) -> str: ...
```

`format_tool_result` 以 `response.result_state` 為主要分流，優先從 response payload 取資料，對 `cmd` 的依賴限於 display label（tool_name、namespace/resource_name）。

---

## Error Handling

**bot.py handler 內的處理層次：**

```
ParseError (UnknownCommandError / UsageError)
    → format_parse_error → say(thread_ts)
    → return

DispatchError (allowlist violation)
    → format deny message → say(thread_ts)
    → return

runner result_state = failed / denied / fallback / partial
    → format_tool_result → say(thread_ts)

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
| `test_dispatcher.py` | 欄位映射、cluster 永遠從 config 來、allowlist deny、`request_id` 格式 |
| `test_formatter.py` | 每種 `result_state`、每種 `ParseError`、`supported_tools` 排序穩定 |

---

## MVP 限制

- 只支援 `get_pod_status` 和 `get_pod_events`
- 只支援 staging cluster（production 不在 MVP 範圍）
- 不做 dedup / rate limit / cooldown（Phase 2）
- 不做 user permission mapping（Phase 2）
- 不做 rich blocks（後續視需要加）
- Slack SDK error 不重試

---

## 後續演進項目

- 加入 `get_deployment_status`、`get_recent_logs`、`query_prometheus`（grammar 不需改，register 新 tool 即可）
- user permission / namespace 存取控制（依 Slack user ID 限制可查 namespace）
- dedup / rate limit（同一使用者短時間大量查詢）
- async worker（多 pod 水平擴展時）
- Slack Block Kit 格式化（改善可讀性）
- production cluster 上線（先 shadow mode 觀察）
