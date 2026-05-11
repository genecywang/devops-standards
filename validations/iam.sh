#!/usr/bin/env bash
set -euo pipefail

policy_files="$(find . -path './.git' -prune -o -path './openspec/*' -prune -o -name '*.json' -print | sort)"

if [ -z "$policy_files" ]; then
  echo "iam: no JSON files found, skipping"
  exit 0
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "iam: jq command not found"
  exit 1
fi

found_policy=0

while IFS= read -r file; do
  jq empty "$file" >/dev/null
  if jq -e 'has("Statement") or has("Version")' "$file" >/dev/null; then
    found_policy=1
    echo "iam: inspect $file"
    if jq -e '.. | objects | select(has("Action")) | .Action | arrays? // empty | index("*")' "$file" >/dev/null; then
      echo "iam: warning wildcard Action in $file"
    fi
    if jq -e '.. | objects | select(has("Action")) | .Action | strings? | select(. == "*")' "$file" >/dev/null; then
      echo "iam: warning wildcard Action in $file"
    fi
    if jq -e '.. | objects | select(has("Resource")) | .Resource | arrays? // empty | index("*")' "$file" >/dev/null; then
      echo "iam: warning wildcard Resource in $file"
    fi
    if jq -e '.. | objects | select(has("Resource")) | .Resource | strings? | select(. == "*")' "$file" >/dev/null; then
      echo "iam: warning wildcard Resource in $file"
    fi
  fi
done <<< "$policy_files"

if [ "$found_policy" = "0" ]; then
  echo "iam: no policy-like JSON files found, skipping"
fi
