#!/usr/bin/env bash
set -euo pipefail

HOOK_MODE=0

for arg in "$@"; do
  case "$arg" in
    --hook)
      HOOK_MODE=1
      ;;
    -h|--help)
      cat <<'USAGE'
Usage: scripts/check-codex-workflow.sh [--hook]

Checks whether the local Codex workflow environment is ready.

Options:
  --hook   Emit Codex hook JSON and always exit 0.
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

failures=()
warnings=()
infos=()

add_failure() {
  failures+=("$1")
}

add_warning() {
  warnings+=("$1")
}

add_info() {
  infos+=("$1")
}

json_escape() {
  sed \
    -e 's/\\/\\\\/g' \
    -e 's/"/\\"/g' \
    -e ':a' \
    -e 'N' \
    -e '$!ba' \
    -e 's/\n/\\n/g'
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

check_node() {
  if ! command -v node >/dev/null 2>&1; then
    add_failure "node is not installed; OpenSpec requires Node.js 20.19.0 or newer"
    return
  fi

  local node_version
  node_version="$(node --version)"
  if version_at_least "$node_version" "20.19.0"; then
    add_info "node $node_version"
  else
    add_failure "node $node_version is too old; OpenSpec requires Node.js 20.19.0 or newer"
  fi
}

check_openspec() {
  if ! command -v openspec >/dev/null 2>&1; then
    add_warning "openspec is not installed; run scripts/bootstrap-codex-workflow.sh --install-openspec"
    return
  fi

  local openspec_version
  openspec_version="$(openspec --version 2>/dev/null || true)"
  if [ -n "$openspec_version" ]; then
    add_info "openspec $openspec_version"
  else
    add_warning "openspec command exists but version check failed"
  fi
}

check_codex_config() {
  if [ ! -f ".codex/config.toml" ]; then
    add_warning ".codex/config.toml is missing; run scripts/bootstrap-codex-workflow.sh"
    return
  fi

  if grep -q 'codex_hooks = true' ".codex/config.toml"; then
    add_info "codex hooks enabled in .codex/config.toml"
  else
    add_warning ".codex/config.toml exists but codex_hooks is not enabled"
  fi

  local skill
  for skill in skills/architecture-review skills/security-review skills/operational-risk-review; do
    if grep -q "$skill" ".codex/config.toml"; then
      add_info "codex skill enabled: $skill"
    else
      add_warning ".codex/config.toml does not reference $skill"
    fi
  done
}

check_repo_skills() {
  local skill
  for skill in skills/architecture-review skills/security-review skills/operational-risk-review; do
    if [ -f "$skill/SKILL.md" ]; then
      add_info "repo skill present: $skill"
    else
      add_failure "repo skill missing: $skill/SKILL.md"
    fi
  done
}

check_superpowers() {
  local codex_home
  codex_home="${CODEX_HOME:-$HOME/.codex}"

  if [ -d "$codex_home/superpowers/skills" ]; then
    add_info "superpowers skills found at $codex_home/superpowers/skills"
  else
    add_warning "superpowers skills not found under $codex_home/superpowers/skills; install or enable the Superpower plugin if this is a new machine"
  fi
}

check_validation_scripts() {
  local script
  for script in validations/all.sh validations/terraform.sh validations/helm.sh validations/kubernetes.sh validations/iam.sh; do
    if [ ! -f "$script" ]; then
      add_failure "validation script missing: $script"
      continue
    fi
    if [ ! -x "$script" ]; then
      add_warning "validation script is not executable: $script"
    else
      add_info "validation script executable: $script"
    fi
  done
}

check_openspec_files() {
  local path
  for path in openspec/config.yaml openspec/specs/ai-coding-workflow/spec.md openspec/specs/infra-change-management/spec.md; do
    if [ -f "$path" ]; then
      add_info "openspec file present: $path"
    else
      add_failure "openspec file missing: $path"
    fi
  done
}

print_human_report() {
  echo "Codex workflow check"
  echo "repo: $repo_root"
  echo

  if [ "${#infos[@]}" -gt 0 ]; then
    echo "OK:"
    printf '  - %s\n' "${infos[@]}"
    echo
  fi

  if [ "${#warnings[@]}" -gt 0 ]; then
    echo "Warnings:"
    printf '  - %s\n' "${warnings[@]}"
    echo
  fi

  if [ "${#failures[@]}" -gt 0 ]; then
    echo "Failures:"
    printf '  - %s\n' "${failures[@]}"
    echo
  fi
}

print_hook_report() {
  if [ "${#failures[@]}" -eq 0 ] && [ "${#warnings[@]}" -eq 0 ]; then
    exit 0
  fi

  local message
  message="Codex workflow setup needs attention."

  if [ "${#failures[@]}" -gt 0 ]; then
    message+=$'\nFailures:'
    local failure
    for failure in "${failures[@]}"; do
      message+=$'\n- '"$failure"
    done
  fi

  if [ "${#warnings[@]}" -gt 0 ]; then
    message+=$'\nWarnings:'
    local warning
    for warning in "${warnings[@]}"; do
      message+=$'\n- '"$warning"
    done
  fi

  message+=$'\nRun scripts/bootstrap-codex-workflow.sh after reviewing the impact.'

  local escaped
  escaped="$(printf '%s' "$message" | json_escape)"
  printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' "$escaped"
}

check_node
check_openspec
check_codex_config
check_repo_skills
check_superpowers
check_validation_scripts
check_openspec_files

if [ "$HOOK_MODE" -eq 1 ]; then
  print_hook_report
  exit 0
fi

print_human_report

if [ "${#failures[@]}" -gt 0 ]; then
  exit 1
fi

exit 0
