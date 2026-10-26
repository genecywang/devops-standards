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
    -e ':a' \
    -e '$!{' \
    -e 'N' \
    -e 'ba' \
    -e '}' \
    -e 's/\\/\\\\/g' \
    -e 's/"/\\"/g' \
    -e $'s/\t/\\\\t/g' \
    -e $'s/\r/\\\\r/g' \
    -e 's/\n/\\n/g'
}

check_codex_config() {
  if [ ! -f ".codex/config.toml" ]; then
    add_warning ".codex/config.toml is missing; run scripts/bootstrap-codex-workflow.sh"
    return
  fi

  if ! command -v python3 >/dev/null 2>&1; then
    add_warning "Codex config inspection skipped: Python 3.11+ required"
    return
  fi

  local report level message
  if ! report="$(python3 "$repo_root/scripts/check-codex-config.py" 2>/dev/null)"; then
    add_warning "Codex config inspection failed; no configuration values were printed"
    return
  fi
  while IFS=$'\t' read -r level message; do
    case "$level" in
      info) add_info "$message" ;;
      warning) add_warning "$message" ;;
    esac
  done <<< "$report"
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
  local codex_home candidate
  codex_home="${CODEX_HOME:-$HOME/.codex}"
  for candidate in \
    "$repo_root/.agents/skills/superpowers" \
    "$HOME/.agents/skills/superpowers" \
    "$codex_home/skills/superpowers" \
    "$codex_home/superpowers/skills"; do
    if [ -f "$candidate/using-superpowers/SKILL.md" ]; then
      add_info "optional Superpowers discovered at $candidate (activation not checked)"
      return
    fi
  done
  add_info "optional Superpowers not discovered in known local paths; no installation required"
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

check_codex_config
check_repo_skills
check_superpowers
check_validation_scripts

if [ "$HOOK_MODE" -eq 1 ]; then
  print_hook_report
  exit 0
fi

print_human_report

if [ "${#failures[@]}" -gt 0 ]; then
  exit 1
fi

exit 0
