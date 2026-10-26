# Claude Code macOS 採用指引

本文件只描述設定範圍；讀取文件不代表授權安裝套件或修改全域設定。舊版自動寫入 shell、切換 bypass mode、安裝整組 skills 與 statusline 的配方已退役，歷史內容可從 Git 查回。

## 個人 baseline

在本 repo 預覽需要的同步：

```zsh
scripts/sync-personal-ai-config.sh --claude-only --dry-run
```

使用者明確要求同步後才執行：

```zsh
scripts/sync-personal-ai-config.sh --claude-only
```

此操作將 `~/.claude/CLAUDE.md` 連到 [global template](../templates/claude/CLAUDE.global.md)，不改 `settings.json`。目的地已存在時先檢視差異；僅在授權替換時使用 `--force`，由腳本備份。

## Project-local 設定

- 依 target repo 的實際部署與 validation 路徑維護 `CLAUDE.md`，不要直接 symlink 個人 global 檔當作 project-local 指引。
- [Claude settings example](../templates/claude/settings.example.json) 是供 review 的 guardrail 範例，不是完整的安全隔離。不要直接覆寫既有 settings，也不要為了減少提問預設開啟 permission bypass。
- 個人 launcher、shell alias、statusline 與 plugin 選擇不屬於這份 baseline；只在使用者另行要求時配置。
- Skills 依實際任務選用，不必安裝固定套件組。既有 `/install-skills` 可繼續處理明確的安裝請求。

## 驗證與 rollback

確認 global symlink 的目標正確，並在新 session 檢查規範是否載入。這不是測試 Claude runtime permissions；若有修改 settings，須另依實際版本與設定層級驗證。

需要 rollback 時，檢視原檔／備份後恢復該次變更；不要以批次覆寫或刪除使用者設定還原。Production/shared-state、權限與 credential 操作仍遵守 global baseline。
