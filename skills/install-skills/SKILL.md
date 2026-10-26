---
name: install-skills
description: Use when the user explicitly requests a Codex or Claude Code skill/plugin installation, update, or installation inventory. Excludes ordinary tasks and automatic missing-skill reminders.
---

# Install Skills

處理使用者明確要求的 Codex／Claude Code skill 或 plugin 安裝與盤點。這是共用的選用入口，不維護固定 required/recommended 套件清單，也不因出現技術關鍵字就要求安裝。

## Client 路由

- 優先從目前 session 判斷目標 client；使用者明確指定另一個 client 時以其要求為準，不同時安裝兩邊。
- Codex：若有內建 `skill-installer`，依其指引處理 curated 或 repo skill 安裝；plugin 則優先使用可用的 plugin-management 工具。這份 `install-skills` 是需求與範圍入口，不取代官方安裝器，也不遞迴呼叫自己。
- Claude Code：依目前官方支援的 skill／plugin 安裝方式處理；不要直接套用 Codex 的工具或設定。若 session 無法執行必要的 client command，提供具體命令並明確說明尚未安裝。
- 使用者只問如何選用已安裝的 Superpowers 時，說明適合的 skill 與啟用方式，不重新安裝、停用整包或改設定。選用單個 skill 不代表其 references／相依 skills 都可以省略。

## 範圍與來源

- 辨識請求的 skill／plugin、目標 client 與 user/project scope。僅盤點時保持唯讀；單獨呼叫入口且沒有指定安裝目標時，只盤點或詢問目標，不擅自安裝。
- 從官方來源或使用者指定 repo 驗證目前支援的安裝方式、所需檔案與版本。不要只下載 `SKILL.md` 就假定 scripts/references 已齊全。
- 只有缺少會影響選擇的資訊時才詢問。不要把單一安裝請求擴大成整包安裝，也不要假設別的 client 的安裝格式相同。

## 執行與驗證

- 安裝前提供明確來源、目的地、寫入範圍與所需相依；已授權的相同範圍不重複詢問。既有檔案不自動覆寫，先比較並取得替換授權，保留可回復備份。
- 依可用的官方工具完成已授權工作；不變更模型、permission mode 或無關 hooks，不讀取或輸出 credentials。
- 驗證 artifact 完整、metadata 有效且 client 能發現它；未驗證 runtime discovery 時明確說明。回報實際安裝結果與 rollback 方法。

舊 `catalog.json` 已退役；`check-skills.sh` 僅保留為靜默相容入口。不要新增其 `UserPromptSubmit` hook。若使用者要求移除舊 hook，只處理對應項目並保留其他 settings。
