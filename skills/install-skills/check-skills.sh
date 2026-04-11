#!/usr/bin/env bash
# check-skills.sh — 偵測缺少的 skills 並提示使用者
# 供 Claude Code UserPromptSubmit hook 使用

CATALOG="$HOME/.claude/skills/install-skills/catalog.json"
SKILLS_DIR="$HOME/.claude/skills"

# catalog 不存在則略過
[[ -f "$CATALOG" ]] || exit 0

# 取得 catalog 中的 skill 名稱（排除 install-skills 本身）
CATALOG_SKILLS=$(python3 -c "
import json, sys
with open('$CATALOG') as f:
    data = json.load(f)
for s in data['skills']:
    if s['name'] != 'install-skills':
        print(s['name'])
" 2>/dev/null)

[[ -z "$CATALOG_SKILLS" ]] && exit 0

# 比對已安裝
MISSING=()
while IFS= read -r skill; do
    if [[ ! -f "$SKILLS_DIR/$skill/SKILL.md" ]]; then
        MISSING+=("$skill")
    fi
done <<< "$CATALOG_SKILLS"

# 有缺少才輸出
if [[ ${#MISSING[@]} -gt 0 ]]; then
    echo "[install-skills] 偵測到以下 skills 尚未安裝：${MISSING[*]}"
    echo "[install-skills] 執行 /install-skills 進行安裝。"
fi
