---
name: install-skills
description: Install and manage Claude Code skills in a new or existing environment. Use this skill proactively when the user is setting up a new machine, mentions missing skills, asks about available skills, or types /install-skills. Also suggest using this skill when you notice a skill referenced in CLAUDE.md or conversation is not installed.
---

# Install Skills

幫助使用者在新環境快速安裝 Claude Code skills，以互動式勾選方式進行。

## 流程

### Step 1：掃描已安裝的 skills

執行以下兩個指令：

```bash
# 格式 A/B：手動安裝的 skills
ls ~/.claude/skills/ 2>/dev/null || echo "(none)"

# 格式 C：plugin 安裝的 plugins
cat ~/.claude/plugins/installed_plugins.json 2>/dev/null || echo "{}"
```

### Step 2：載入 catalog

讀取此 skill 同目錄下的 `catalog.json`，取得完整 skills 清單與優先級。

catalog 路徑：`~/.claude/skills/install-skills/catalog.json`

### Step 3：比對並呈現狀態

以表格形式呈現比對結果：

```
Skills 安裝狀態
────────────────────────────────────────────────
 [已安裝] skill-creator     建立與優化 skills        required
 [已安裝] install-skills    環境 setup              required
 [缺少]   claude-api        Claude API 開發          recommended
 [缺少]   pdf               PDF 處理                recommended
 [缺少]   xlsx              Excel 操作               recommended
 [缺少]   mcp-builder       建立 MCP server          optional
 [缺少]   webapp-testing    Web 應用測試              optional
────────────────────────────────────────────────
```

### Step 4：互動式選擇

詢問使用者要安裝哪些 skills。提供以下快速選項：

- **全部安裝**：安裝所有缺少的 skills
- **只裝 required + recommended**：略過 optional
- **自選**：列出缺少的 skills，請使用者用編號或名稱指定

範例提示：
```
要安裝哪些？
  1. 全部（3 個）
  2. 只裝 recommended（claude-api, pdf, xlsx）
  3. 自選（輸入編號，如 1 3 5）
```

### Step 5：安裝

catalog entry 有兩種格式，安裝邏輯不同：

#### 格式 A：單一 skill（有 `path` 欄位，無 `skills` 陣列）

`source` 欄位為完整 GitHub URL（`https://github.com/owner/repo`），每個 entry 均需明確填寫，取出 `owner/repo` 部分作為 raw URL 的路徑：

```bash
SKILL_NAME="<skill-name>"
SKILL_PATH="<path-from-catalog>"
REPO="<entry.source 的 owner/repo，如 microsoft/playwright-cli>"
mkdir -p ~/.claude/skills/${SKILL_NAME}
curl -s "https://raw.githubusercontent.com/${REPO}/main/${SKILL_PATH}/SKILL.md" \
  -o ~/.claude/skills/${SKILL_NAME}/SKILL.md
```

#### 格式 B：Multi-skill bundle（有 `skills` 陣列與 `source` 欄位）

從 `source` repo 安裝每個子 skill：

```bash
REPO="<source repo，如 nextlevelbuilder/ui-ux-pro-max-skill>"
# 對 skills 陣列中每個項目執行：
SKILL_NAME="<skills[i].name>"
SKILL_PATH="<skills[i].path>"
mkdir -p ~/.claude/skills/${SKILL_NAME}
curl -s "https://raw.githubusercontent.com/${REPO}/main/${SKILL_PATH}/SKILL.md" \
  -o ~/.claude/skills/${SKILL_NAME}/SKILL.md
```

Step 3 呈現狀態時，bundle entry 展開為各子 skill 逐行列出，`[已安裝]` 判斷以各子 skill 目錄是否存在為準。

安裝完畢後確認檔案存在：

```bash
ls ~/.claude/skills/${SKILL_NAME}/SKILL.md
```

#### 格式 C：Plugin 安裝（有 `install_method: "plugin"` 欄位）

這類 entry 無法由 Claude 代為執行，需提示使用者自行依序輸入。

entry 可能有兩種欄位：
- `install_command`（字串）：單一指令
- `install_commands`（陣列）：多個指令，需依序執行

範例提示：
```
「ui-ux-pro-max」使用 plugin 方式安裝，請在 Claude Code 依序輸入：
1. /plugin marketplace add nextlevelbuilder/ui-ux-pro-max-skill
2. /plugin install ui-ux-pro-max@ui-ux-pro-max-skill
```

Step 3 呈現狀態時，plugin entry 的 `[已安裝]` 判斷方式：

```bash
# 從 install_command 取出 plugin key（即 install_command 的最後一個參數）
# 例如：/plugin install superpowers@claude-plugins-official → key = "superpowers@claude-plugins-official"
cat ~/.claude/plugins/installed_plugins.json | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(list(data.get('plugins', {}).keys()))
"
```

若 plugin key 存在於 `plugins` 物件中，顯示 `[已安裝]`；否則顯示 `[缺少]`。

### Step 6：回報結果

列出本次安裝結果（成功 / 失敗），並提醒：

> 重新啟動 Claude Code session 後，新安裝的 skills 才會生效。

---

## 錯誤處理

- **curl 失敗**：可能是網路問題或 VPN 未連線，提示使用者確認後重試
- **目錄無法建立**：確認 `~/.claude/skills/` 權限
- **SKILL.md 為空**：重新嘗試，或跳過該 skill 並告知使用者

---

## 更新 catalog

catalog 位於 `~/.claude/skills/install-skills/catalog.json`。

若使用者想新增或移除 catalog 中的 skill，直接編輯該 JSON 即可。每個格式 A entry 均需明確填寫 `source`（完整 GitHub URL），不依賴頂層 `source` 作為回退。頂層 `source` 欄位保留為文件說明用途，安裝邏輯不使用。

---

## Startup 偵測（Hook 設定）

若要在每次 session 啟動時自動偵測缺少的 skills，可在 `~/.claude/settings.json` 加入以下 hook：

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/skills/install-skills/check-skills.sh"
          }
        ]
      }
    ]
  }
}
```

check-skills.sh 會比對 catalog 與已安裝清單，若有缺漏則輸出提示訊息。使用者可選擇是否要求 Claude 繼續安裝。
