#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
script="$repo_root/scripts/sync-personal-ai-config.sh"
tmpdirs_file="$(mktemp)"

cleanup() {
  local tmpdir
  while IFS= read -r tmpdir; do
    if [ -n "$tmpdir" ] && [ -d "$tmpdir" ]; then
      command rm -rf "$tmpdir"
    fi
  done < "$tmpdirs_file"
  command rm -f "$tmpdirs_file"
}
trap cleanup EXIT

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

assert_file_contains() {
  local file="$1"
  local expected="$2"

  [ -f "$file" ] || fail "expected file to exist: $file"
  grep -Fq "$expected" "$file" || fail "expected $file to contain: $expected"
}

assert_symlink_target() {
  local link_path="$1"
  local expected_target="$2"

  [ -L "$link_path" ] || fail "expected symlink: $link_path"

  local actual_target
  actual_target="$(readlink "$link_path")"
  [ "$actual_target" = "$expected_target" ] || fail "expected $link_path -> $expected_target, got $actual_target"
}

run_sync() {
  local codex_home="$1"
  local claude_home="$2"
  shift 2

  CODEX_HOME="$codex_home" CLAUDE_HOME="$claude_home" "$script" "$@"
}

make_tmpdir() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  printf '%s\n' "$tmpdir" >> "$tmpdirs_file"
  printf '%s\n' "$tmpdir"
}

test_creates_global_instruction_and_skill_links() {
  local tmpdir
  tmpdir="$(make_tmpdir)"

  local codex_home="$tmpdir/codex"
  local claude_home="$tmpdir/claude"

  if ! run_sync "$codex_home" "$claude_home" >"$tmpdir/stdout" 2>"$tmpdir/stderr"; then
    cat "$tmpdir/stdout" >&2
    cat "$tmpdir/stderr" >&2
    fail "expected sync to create global instruction and skill links"
  fi

  assert_symlink_target "$codex_home/AGENTS.md" "$repo_root/templates/codex/AGENTS.global.md"
  assert_symlink_target "$claude_home/CLAUDE.md" "$repo_root/templates/claude/CLAUDE.global.md"
  assert_symlink_target "$codex_home/skills/gene-devops-architecture-review" "$repo_root/skills/architecture-review"
  assert_symlink_target "$codex_home/skills/gene-devops-security-review" "$repo_root/skills/security-review"
  assert_symlink_target "$codex_home/skills/gene-devops-operational-risk-review" "$repo_root/skills/operational-risk-review"
}

test_existing_file_is_not_overwritten_without_force() {
  local tmpdir
  tmpdir="$(make_tmpdir)"

  local codex_home="$tmpdir/codex"
  local claude_home="$tmpdir/claude"
  mkdir -p "$codex_home" "$claude_home"
  printf 'keep me\n' >"$codex_home/AGENTS.md"

  if run_sync "$codex_home" "$claude_home" >"$tmpdir/stdout" 2>"$tmpdir/stderr"; then
    fail "expected sync to fail when destination exists without --force"
  fi

  assert_file_contains "$codex_home/AGENTS.md" "keep me"
}

test_force_backs_up_existing_files_before_linking() {
  local tmpdir
  tmpdir="$(make_tmpdir)"

  local codex_home="$tmpdir/codex"
  local claude_home="$tmpdir/claude"
  mkdir -p "$codex_home" "$claude_home"
  printf 'old codex\n' >"$codex_home/AGENTS.md"
  printf 'old claude\n' >"$claude_home/CLAUDE.md"

  if ! run_sync "$codex_home" "$claude_home" --force >"$tmpdir/stdout" 2>"$tmpdir/stderr"; then
    cat "$tmpdir/stdout" >&2
    cat "$tmpdir/stderr" >&2
    fail "expected --force sync to back up existing files and create links"
  fi

  assert_symlink_target "$codex_home/AGENTS.md" "$repo_root/templates/codex/AGENTS.global.md"
  assert_symlink_target "$claude_home/CLAUDE.md" "$repo_root/templates/claude/CLAUDE.global.md"

  compgen -G "$codex_home/AGENTS.md.bak.*" >/dev/null || fail "expected backup for Codex AGENTS.md"
  compgen -G "$claude_home/CLAUDE.md.bak.*" >/dev/null || fail "expected backup for Claude CLAUDE.md"
}

test_dry_run_does_not_create_links() {
  local tmpdir
  tmpdir="$(make_tmpdir)"

  local codex_home="$tmpdir/codex"
  local claude_home="$tmpdir/claude"

  if ! run_sync "$codex_home" "$claude_home" --dry-run >"$tmpdir/stdout" 2>"$tmpdir/stderr"; then
    cat "$tmpdir/stdout" >&2
    cat "$tmpdir/stderr" >&2
    fail "expected --dry-run sync to succeed without writing files"
  fi

  [ ! -e "$codex_home/AGENTS.md" ] || fail "dry-run created Codex AGENTS.md"
  [ ! -e "$claude_home/CLAUDE.md" ] || fail "dry-run created Claude CLAUDE.md"
  assert_file_contains "$tmpdir/stdout" "would link:"
}

test_creates_global_instruction_and_skill_links
test_existing_file_is_not_overwritten_without_force
test_force_backs_up_existing_files_before_linking
test_dry_run_does_not_create_links

echo "sync-personal-ai-config tests passed"
