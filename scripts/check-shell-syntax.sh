#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ "$#" -eq 0 ]; then
  set -- "$repo_root"/scripts/*.sh "$repo_root"/validations/*.sh "$repo_root"/tests/*.sh
fi
for file in "$@"; do
  bash -n "$file"
done
echo "shell syntax checks passed"
