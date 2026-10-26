#!/usr/bin/env bash
set -euo pipefail

FORCE=0
DRY_RUN=0
SYNC_CODEX=1
SYNC_CLAUDE=1
SYNC_SKILLS=1
SYNC_INSTALLER=0
MIGRATE=0
PREFLIGHT=1
CLIENT_SELECTION=""

usage() {
  cat <<'USAGE'
Usage: scripts/sync-personal-ai-config.sh [options]

Synchronizes personal global AI assistant configuration from this repository.

Default behavior:
  - Link ~/.codex/AGENTS.md to templates/codex/AGENTS.global.md
  - Link ~/.claude/CLAUDE.md to templates/claude/CLAUDE.global.md
  - Link workflows, prompts, validations under each selected client home/standards/
  - Link namespaced DevOps review skills into ~/.agents/skills/
  - Do not modify config.toml, settings.json, secrets, or credentials

Options:
  --migrate-legacy-skills  Back up owned legacy review links outside skill discovery.
  --force        Back up existing destinations before replacing them.
  --dry-run      Print planned changes without writing files.
  --codex-only   Sync Codex files only.
  --claude-only  Sync Claude Code files only.
  --with-skills  Sync namespaced Codex skill symlinks. This is the default.
  --no-skills    Do not sync Codex review skill symlinks.
  --with-installer  Also link the optional install-skills entry for selected clients.
  -h, --help     Show this help.

Codex review skills also use CODEX_USER_SKILLS_DIR.
Optional installer destinations:
  Codex: ${CODEX_USER_SKILLS_DIR:-$HOME/.agents/skills}/gene-devops-install-skills
  Claude: ${CLAUDE_HOME:-$HOME/.claude}/skills/install-skills
  --no-skills does not disable an explicitly requested --with-installer.
USAGE
}

for arg in "$@"; do
  case "$arg" in
    --force)
      FORCE=1
      ;;
    --dry-run)
      DRY_RUN=1
      ;;
    --migrate-legacy-skills)
      MIGRATE=1
      ;;
    --codex-only)
      [ "$CLIENT_SELECTION" != claude ] || { echo "conflicting client flags" >&2; exit 2; }
      CLIENT_SELECTION=codex
      SYNC_CODEX=1
      SYNC_CLAUDE=0
      ;;
    --claude-only)
      [ "$CLIENT_SELECTION" != codex ] || { echo "conflicting client flags" >&2; exit 2; }
      CLIENT_SELECTION=claude
      SYNC_CODEX=0
      SYNC_CLAUDE=1
      ;;
    --with-skills)
      SYNC_SKILLS=1
      ;;
    --no-skills)
      SYNC_SKILLS=0
      ;;
    --with-installer)
      SYNC_INSTALLER=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $arg" >&2
      usage >&2
      exit 2
      ;;
  esac
done

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
codex_home="${CODEX_HOME:-$HOME/.codex}"
claude_home="${CLAUDE_HOME:-$HOME/.claude}"
codex_user_skills_dir="${CODEX_USER_SKILLS_DIR:-$HOME/.agents/skills}"
timestamp="$(date +%Y%m%d%H%M%S)"

log() {
  printf '%s\n' "$*"
}

run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    log "dry-run: $*"
    return 0
  fi

  "$@"
}

check_parent() {
  local parent
  parent="$(dirname "$1")"
  while [ ! -e "$parent" ] && [ ! -L "$parent" ]; do parent="$(dirname "$parent")"; done
  [ -d "$parent" ] || { echo "invalid parent: $parent" >&2; exit 1; }
}

backup_destination() {
  local destination="$1"
  case "$destination" in
    "$codex_user_skills_dir"/*) printf '%s/%s.bak.%s' "$codex_home/skill-backups" "$(basename "$destination")" "$timestamp" ;;
    "$claude_home/skills"/*) printf '%s/%s.bak.%s' "$claude_home/skill-backups" "$(basename "$destination")" "$timestamp" ;;
    *) printf '%s.bak.%s' "$destination" "$timestamp" ;;
  esac
}

backup_path() {
  local destination="$1"
  local backup
  backup="$(backup_destination "$destination")"
  local original_backup="$backup"
  local counter=1

  while [ -e "$backup" ] || [ -L "$backup" ]; do
    backup="${original_backup}.${counter}"
    counter=$((counter + 1))
  done

  if [ "$DRY_RUN" -eq 1 ]; then
    log "would backup: $destination -> $backup"
    return 0
  fi

  mkdir -p "$(dirname "$backup")"
  mv "$destination" "$backup"
  log "backup: $destination -> $backup"
}

ensure_parent_dir() {
  local destination="$1"
  local parent
  parent="$(dirname "$destination")"
  run mkdir -p "$parent"
}

ensure_symlink() {
  local source="$1"
  local destination="$2"
  local label="$3"

  if [ ! -e "$source" ]; then
    echo "missing source for $label: $source" >&2
    exit 1
  fi

  if [ "$PREFLIGHT" -eq 1 ]; then
    check_parent "$destination"
    if [ -e "$destination" ] || [ -L "$destination" ]; then
      if [ "$destination" -ef "$source" ] && [ -L "$destination" ]; then return 0; fi
      [ "$FORCE" -eq 1 ] || { echo "destination conflict: $destination; use --force to back up" >&2; exit 1; }
      check_parent "$(backup_destination "$destination")"
    fi
    return 0
  fi

  ensure_parent_dir "$destination"

  if [ -L "$destination" ]; then
    local current_target
    current_target="$(readlink "$destination")"

    if [ "$destination" -ef "$source" ]; then
      log "ok: $label already linked"
      return 0
    fi

    if [ "$FORCE" -ne 1 ]; then
      echo "destination exists with different symlink target: $destination -> $current_target" >&2
      echo "rerun with --force to back it up and replace it" >&2
      exit 1
    fi

    backup_path "$destination"
  elif [ -e "$destination" ]; then
    if [ "$FORCE" -ne 1 ]; then
      echo "destination exists and will not be overwritten: $destination" >&2
      echo "rerun with --force to back it up and replace it" >&2
      exit 1
    fi

    backup_path "$destination"
  fi

  if [ "$DRY_RUN" -eq 1 ]; then
    log "would link: $destination -> $source"
    return 0
  fi

  ln -s "$source" "$destination"
  log "linked: $destination -> $source"
}

sync_resources() {
  local client_home="$1"
  local resource
  for resource in workflows prompts validations; do
    ensure_symlink "$repo_root/$resource" "$client_home/standards/$resource" "global standards $resource"
  done
}

sync_codex() {
  ensure_symlink \
    "$repo_root/templates/codex/AGENTS.global.md" \
    "$codex_home/AGENTS.md" \
    "Codex global AGENTS.md"
  sync_resources "$codex_home"
}

sync_claude() {
  ensure_symlink \
    "$repo_root/templates/claude/CLAUDE.global.md" \
    "$claude_home/CLAUDE.md" \
    "Claude Code global CLAUDE.md"
  sync_resources "$claude_home"
}

sync_codex_skills() {
  ensure_symlink \
    "$repo_root/skills/architecture-review" \
    "$codex_user_skills_dir/gene-devops-architecture-review" \
    "Codex architecture review skill"

  ensure_symlink \
    "$repo_root/skills/security-review" \
    "$codex_user_skills_dir/gene-devops-security-review" \
    "Codex security review skill"

  ensure_symlink \
    "$repo_root/skills/operational-risk-review" \
    "$codex_user_skills_dir/gene-devops-operational-risk-review" \
    "Codex operational risk review skill"
}

sync_selected() {
if [ "$SYNC_CODEX" -eq 1 ]; then
  sync_codex
fi

if [ "$SYNC_CLAUDE" -eq 1 ]; then
  sync_claude
fi

if [ "$SYNC_CODEX" -eq 1 ] && [ "$SYNC_SKILLS" -eq 1 ]; then
  sync_codex_skills
fi

if [ "$SYNC_INSTALLER" -eq 1 ]; then
  if [ "$SYNC_CODEX" -eq 1 ]; then
    ensure_symlink \
      "$repo_root/skills/install-skills" \
      "$codex_user_skills_dir/gene-devops-install-skills" \
      "Codex optional install-skills entry"
  fi
  if [ "$SYNC_CLAUDE" -eq 1 ]; then
    ensure_symlink \
      "$repo_root/skills/install-skills" \
      "$claude_home/skills/install-skills" \
      "Claude optional install-skills entry"
  fi
fi

}

# Validate the entire write set before creating directories, backups, or links.
sync_selected
if [ "$MIGRATE" -eq 1 ]; then
  [ "$SYNC_CODEX" -eq 1 ] && [ "$SYNC_SKILLS" -eq 1 ] || { echo "migration requires Codex review skills" >&2; exit 2; }
  for name in architecture-review security-review operational-risk-review; do
    legacy="$codex_home/skills/gene-devops-$name"
    if [ -e "$legacy" ] || [ -L "$legacy" ]; then
      [ -L "$legacy" ] && [ "$legacy" -ef "$repo_root/skills/$name" ] || { echo "refusing migration of unowned legacy entry: $legacy" >&2; exit 1; }
      check_parent "$codex_home/skill-backups/$timestamp/gene-devops-$name"
    fi
  done
fi
PREFLIGHT=0
sync_selected
if [ "$MIGRATE" -eq 1 ]; then
  for name in architecture-review security-review operational-risk-review; do
    legacy="$codex_home/skills/gene-devops-$name"
    destination="$codex_user_skills_dir/gene-devops-$name"
    if [ -L "$legacy" ] && [ "$(dirname "$legacy")" -ef "$(dirname "$destination")" ]; then continue; fi
    if [ -L "$legacy" ]; then
      backup_dir="$codex_home/skill-backups/$timestamp"
      while [ -e "$backup_dir/gene-devops-$name" ] || [ -L "$backup_dir/gene-devops-$name" ]; do backup_dir="${backup_dir}.next"; done
      run mkdir -p "$backup_dir"
      run mv "$legacy" "$backup_dir/gene-devops-$name"
      log "legacy backup: $backup_dir/gene-devops-$name"
    fi
  done
fi
log "personal AI config sync finished"
