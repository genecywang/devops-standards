#!/usr/bin/env bash
set -euo pipefail

INSTALL_OPENSPEC=0
SKIP_OPENSPEC_INSTALL=0
YES=0

for arg in "$@"; do
  case "$arg" in
    --install-openspec)
      INSTALL_OPENSPEC=1
      ;;
    --skip-openspec-install)
      SKIP_OPENSPEC_INSTALL=1
      ;;
    -y|--yes)
      YES=1
      ;;
    -h|--help)
      cat <<'USAGE'
Usage: scripts/bootstrap-codex-workflow.sh [--install-openspec] [--skip-openspec-install] [--yes]

Bootstraps the local Codex workflow environment.

Options:
  --install-openspec       Install OpenSpec globally when missing.
  --skip-openspec-install  Do not install OpenSpec, even when missing.
  -y, --yes                Do not prompt in interactive mode.
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

confirm() {
  local prompt="$1"

  if [ "$YES" -eq 1 ]; then
    return 0
  fi

  if [ ! -t 0 ]; then
    return 1
  fi

  printf '%s [y/N] ' "$prompt"
  local answer
  read -r answer
  case "$answer" in
    y|Y|yes|YES)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

version_at_least() {
  local current required
  current="${1#v}"
  required="$2"

  local current_major current_minor current_patch
  local required_major required_minor required_patch

  IFS=. read -r current_major current_minor current_patch _ <<< "$current"
  IFS=. read -r required_major required_minor required_patch _ <<< "$required"

  current_major="${current_major:-0}"
  current_minor="${current_minor:-0}"
  current_patch="${current_patch:-0}"
  required_major="${required_major:-0}"
  required_minor="${required_minor:-0}"
  required_patch="${required_patch:-0}"

  if [ "$current_major" -gt "$required_major" ]; then
    return 0
  fi
  if [ "$current_major" -lt "$required_major" ]; then
    return 1
  fi
  if [ "$current_minor" -gt "$required_minor" ]; then
    return 0
  fi
  if [ "$current_minor" -lt "$required_minor" ]; then
    return 1
  fi
  [ "$current_patch" -ge "$required_patch" ]
}

ensure_node() {
  if ! command -v node >/dev/null 2>&1; then
    echo "node is required before installing OpenSpec. Install Node.js 20.19.0 or newer." >&2
    exit 1
  fi

  local node_version
  node_version="$(node --version)"
  if ! version_at_least "$node_version" "20.19.0"; then
    echo "node $node_version is too old. OpenSpec requires Node.js 20.19.0 or newer." >&2
    exit 1
  fi
}

ensure_codex_config() {
  mkdir -p .codex

  if [ -f ".codex/config.toml" ]; then
    echo "codex: .codex/config.toml already exists; not overwriting"
    return
  fi

  if [ ! -f ".codex/config.example.toml" ]; then
    echo "codex: .codex/config.example.toml missing" >&2
    exit 1
  fi

  cp ".codex/config.example.toml" ".codex/config.toml"
  echo "codex: created .codex/config.toml from example"
}

ensure_openspec() {
  if command -v openspec >/dev/null 2>&1; then
    echo "openspec: $(openspec --version 2>/dev/null || echo installed)"
    return
  fi

  if [ "$SKIP_OPENSPEC_INSTALL" -eq 1 ]; then
    echo "openspec: not installed; skipping install by request"
    return
  fi

  if [ "$INSTALL_OPENSPEC" -ne 1 ]; then
    if confirm "OpenSpec is missing. Install globally with npm install -g @fission-ai/openspec@latest?"; then
      INSTALL_OPENSPEC=1
    else
      echo "openspec: missing; run again with --install-openspec when ready"
      return
    fi
  fi

  ensure_node

  if ! command -v npm >/dev/null 2>&1; then
    echo "npm is required for npm-based OpenSpec installation" >&2
    exit 1
  fi

  echo "openspec: installing globally with npm"
  npm install -g @fission-ai/openspec@latest
  echo "openspec: $(openspec --version)"
}

validate_openspec() {
  if ! command -v openspec >/dev/null 2>&1; then
    echo "openspec: validation skipped because CLI is not installed"
    return
  fi

  if [ -d "openspec/changes/bootstrap-codex-claude-workflow" ]; then
    echo "openspec: validate bootstrap-codex-claude-workflow"
    openspec validate bootstrap-codex-claude-workflow --strict
  else
    echo "openspec: bootstrap change not found, skipping change validation"
  fi
}

run_validations() {
  if [ -x "validations/all.sh" ]; then
    echo "validations: run all"
    validations/all.sh
  else
    echo "validations/all.sh is missing or not executable" >&2
    exit 1
  fi
}

ensure_node
ensure_codex_config
ensure_openspec
validate_openspec
run_validations

echo "codex workflow bootstrap finished"
