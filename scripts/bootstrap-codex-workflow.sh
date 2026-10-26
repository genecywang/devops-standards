#!/usr/bin/env bash
set -euo pipefail

for arg in "$@"; do
  case "$arg" in
    -h|--help)
      cat <<'USAGE'
Usage: scripts/bootstrap-codex-workflow.sh

Creates missing repo-local Codex config from its example and checks setup.
Existing config is preserved. No packages are installed and no infrastructure
validation or external operation is run.
USAGE
      exit 0
      ;;
    *)
      echo "unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$repo_root"

if [ -e ".codex/config.toml" ] || [ -L ".codex/config.toml" ]; then
  echo "codex: .codex/config.toml already exists; not overwriting"
else
  if [ ! -f ".codex/config.example.toml" ]; then
    echo "codex: .codex/config.example.toml missing" >&2
    exit 1
  fi
  mkdir -p .codex
  cp .codex/config.example.toml .codex/config.toml
  echo "codex: created .codex/config.toml from example"
fi

bash scripts/check-codex-workflow.sh
echo "codex workflow bootstrap finished"
