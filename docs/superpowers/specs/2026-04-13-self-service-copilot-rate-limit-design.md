# Self-Service Copilot Rate Limit Design

**Date:** 2026-04-13
**Scope:** In-memory rate limiting for `self_service_copilot`
**Status:** Proposed

## Context

`self_service_copilot` 已可在 staging 部署，也已有真實 Slack ingress 與多個 read-only tools。

在第一個真實使用者進來前，缺少最基本的 abuse protection：

- 單一 user 連續 spam
- 單一 channel 短時間流量過高

目前 deployment 固定 `replicas: 1`，所以第一版可接受單 pod in-memory throttle。

## Goals

- 對 Slack bot 增加最小可用的 rate limiting
- 同時保護：
  - `per-user`
  - `per-channel`
- 限流語意貼近「60 秒內最多 N 次」
- 不改動 `openclaw_foundation`

## Non-Goals

- Redis / external state
- multi-replica shared throttle
- per-tool quota
- per-namespace quota
- 持久化 usage history
- 管理後台或 metrics dashboard

---

## 1. Approach

採用 **sliding window**，每個 key 用 `deque[timestamp]` 保存最近一次窗口內的請求時間。

每次請求時：

1. 取出該 key 的 `deque`
2. pop 掉所有超出 window 的舊 timestamp
3. 若目前長度已達 limit，拒絕
4. 否則 append 現在時間，允許通過

這個設計比 fixed window 更符合「60 秒內最多 N 次」語意，也避免 window boundary burst。

---

## 2. Protection Model

第一版同時做兩層：

### Per-user

- key: `user:<actor_id>`
- default: `60 秒 / 5 次`

### Per-channel

- key: `channel:<channel_id>`
- default: `60 秒 / 20 次`

判斷規則：

- 任一 limiter 超限，就拒絕這次 request

這樣可以同時防：

- 單一 user spam
- 多 user 在同一個 channel 把 bot 打爆

---

## 3. Placement

rate limit 邏輯只放在 `self_service_copilot/`，不進 `openclaw_foundation/`。

原因：

- 這是 Slack product ingress policy
- 不是通用 runtime concern
- 未來如果其他 product consume `openclaw_foundation`，不應被 Slack throttle 綁住

建議新增模組：

`self_service_copilot/src/self_service_copilot/rate_limit.py`

責任：

- in-memory limiter data structure
- decision API
- exception / result model

---

## 4. API Shape

建議介面：

```python
@dataclass(frozen=True)
class RateLimitRule:
    limit: int
    window_seconds: int


class RateLimitExceededError(ValueError):
    pass


class SlidingWindowRateLimiter:
    def __init__(self, now_fn: Callable[[], float] | None = None) -> None: ...

    def allow(self, key: str, rule: RateLimitRule) -> bool: ...


class CopilotRateLimiter:
    def __init__(
        self,
        user_rule: RateLimitRule,
        channel_rule: RateLimitRule,
        now_fn: Callable[[], float] | None = None,
    ) -> None: ...

    def check(self, actor_id: str, channel_id: str) -> None: ...
```

`CopilotRateLimiter.check()` 行為：

- 若 user 或 channel 超限，raise `RateLimitExceededError`
- 否則正常返回

---

## 5. Config

透過 env 注入，放進 `CopilotConfig`：

- `COPILOT_USER_RATE_LIMIT_COUNT`
- `COPILOT_USER_RATE_LIMIT_WINDOW_SECONDS`
- `COPILOT_CHANNEL_RATE_LIMIT_COUNT`
- `COPILOT_CHANNEL_RATE_LIMIT_WINDOW_SECONDS`

預設值：

- user: `5 / 60`
- channel: `20 / 60`

這讓 staging 可直接用 default，之後調整不需改 code。

---

## 6. Bot Integration Point

rate limit 檢查放在 `bot.py` 的 mention handler 中，建議順序：

1. channel allowlist check
2. parse command
3. rate limit check
4. dispatcher
5. runner
6. formatter / reply

不在 parse 前檢查的原因：

- 需要 `actor_id` / `channel_id`
- 但仍要盡量早於 dispatcher / runner，避免濫用直接打到 tool layer

對 parse error 是否計入 rate limit：

- **計入**

原因：

- 否則可以用無效指令繞過 throttle 持續打 bot

---

## 7. User-Facing Behavior

超限時回：

```text
[denied] rate limit exceeded, please retry later
```

第一版不區分：

- user 超限
- channel 超限

原因：

- 對使用者不需要暴露太多內部策略
- 訊息保持簡單

log 可保留較細訊息，例如：

- `rate limit exceeded for user U123`
- `rate limit exceeded for channel C123`

---

## 8. Memory Behavior

每個 key 保存最近窗口內的 timestamps。

在目前假設下：

- 單 pod
- staging usage 小
- window 60 秒

記憶體成本可接受。

第一版不額外做背景清理 goroutine / thread。

清理策略：

- 每次 `allow()` 呼叫時，只清該 key 的過期 timestamps

若某些 key 之後完全不再使用，其空 deque 可接受暫留在 dict 中。這是第一版刻意接受的簡化。

---

## 9. Testing

至少覆蓋：

### `rate_limit.py`

- 第一次請求允許
- 視窗內達上限後拒絕
- 視窗外自動恢復
- user / channel 各自獨立計數
- `CopilotRateLimiter.check()` 任一側超限即 raise

### `config.py`

- env default 正確
- env override 正確映射到 `CopilotConfig`

### `bot.py`

- rate limit exceeded 時回 `[denied] rate limit exceeded, please retry later`
- 不會進 runner

測試應透過可注入 `now_fn` 控制時間，不用 `sleep()`

---

## 10. Trade-offs

### Sliding window vs fixed window

選 sliding window，因為：

- 語意更貼近需求
- 不會在 window 邊界 burst

代價是：

- 每個 key 的記憶體不是 O(1)

但在目前 bot 規模下可接受。

### In-memory vs external store

選 in-memory，因為：

- deployment 目前固定 `replicas: 1`
- 成本低
- 實作快

代價是：

- 未來多副本時限流不共享

這是 Phase 2 再解的問題。

---

## 11. Recommended Next Step

這份 spec 對應的 implementation plan 應拆成：

1. `rate_limit.py` + unit tests
2. `config.py` env wiring
3. `bot.py` integration
4. verification + Slack smoke test notes
