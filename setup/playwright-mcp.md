# Playwright MCP Setup

Enables Claude Code to control a browser for web automation and data extraction from pages without APIs.

## What it does

- Navigate to URLs, click elements, fill forms, scroll
- Extract page content, tables, text
- Take screenshots
- Handle login flows, multi-step interactions

## Installation

```bash
# 安裝 Chromium（首次必須）
npx playwright install chromium

mkdir -p ~/.claude/playwright-output

# 寫入 ~/.claude.json（CLI 讀取的 MCP config）
claude mcp add playwright -s user -- \
  npx @playwright/mcp@latest \
  --browser chromium \
  --output-dir ~/.claude/playwright-output
```

> **注意**：MCP servers 必須透過 `claude mcp add` 寫入 `~/.claude.json`。
> 直接編輯 `~/.claude/settings.json` 無效——那個檔案是 desktop app 讀的，不是 CLI。

## Configuration

| Option | Value | Reason |
|---|---|---|
| `--browser` | `chromium` | Best compatibility |
| `--output-dir` | `~/.claude/playwright-output` | Screenshots / snapshots |
| headless | off (default) | See browser actions in real time |

### Switch to headless (for CI or background tasks)

```bash
jq '
  .mcpServers.playwright.args += ["--headless"]
' ~/.claude/settings.json > /tmp/s.json && mv /tmp/s.json ~/.claude/settings.json
```

### Persist login session across runs

```bash
jq '
  .mcpServers.playwright.args += ["--storage-state", "~/.claude/playwright-session.json"]
' ~/.claude/settings.json > /tmp/s.json && mv /tmp/s.json ~/.claude/settings.json
```

## Usage examples

Ask Claude Code:

```
打開 https://example.com，找到價格表格並整理成 CSV
```

```
登入 https://app.example.com，截圖首頁 Dashboard
```

```
每隔 5 分鐘檢查 https://status.example.com 的狀態，有變化時通知我
```

## Output

Screenshots and snapshots are saved to `~/.claude/playwright-output/`.

## Notes

- First run will download Chromium (~150MB) via `npx`
- Headed mode opens a visible browser window — normal behavior
- For pages requiring login, use `--storage-state` to persist session
- Restart Claude Code after modifying `settings.json`
