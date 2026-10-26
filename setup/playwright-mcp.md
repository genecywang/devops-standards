# Playwright MCP：按需設定

此整合是選用項目，不是 DevOps baseline 的必要依賴。只有任務需要瀏覽器自動化且現有工具無法完成時，才評估安裝。讀取此文件不代表授權下載 browser、修改 user config 或讀取登入狀態。

## 設定來源

依目前 client 與所選 scope 使用 [Claude Code MCP 官方文件](https://code.claude.com/docs/en/mcp)。截至 2026-10-26，Claude Code 的 local/user MCP 設定位於 `~/.claude.json`，project scope 位於 repo 的 `.mcp.json`；不要套用舊版指南中對 `~/.claude/settings.json` 的 MCP mutation 範例。

Browser 選擇、headless 與 storage-state 選項以 [Microsoft Playwright MCP 文件](https://github.com/microsoft/playwright-mcp) 為準。避免在此複製整份安裝配方，造成與 upstream 版本漂移。

## 採用邊界

- 安裝前確認 package 來源／版本、client scope、browser profile、輸出位置，以及下載與寫入範圍。
- 先準備具體 config diff 或安裝命令；取得該範圍授權後才執行。保留既有 server 設定，避免用整份 JSON 覆寫。
- Storage state 可能含 cookies 與登入資訊；不得提交、輸出或未經授權讀取。優先使用不含個人登入狀態的測試環境。
- 登入、表單提交、對外訊息或其他外部變更，仍依任務授權處理；browser 可操作不代表已獲授權。

## 驗證與 rollback

安裝後驗證 server 狀態與一個不含敏感資料的唯讀測試頁。不要僅憑 config 已寫入就宣稱連線成功。修改前保留相關設定的備份；rollback 僅撤回該次新增／修改的 server，不批次刪除其他 MCP 或 credentials。
