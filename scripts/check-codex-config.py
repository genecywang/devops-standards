#!/usr/bin/env python3
"""Inspect repo-local hook/skill configuration without printing config values.

Output is a small tab-separated protocol consumed by check-codex-workflow.sh.
This does not resolve Codex's merged user, project, or managed configuration.
"""
import os
from pathlib import Path
import sys


def emit(level, message):
    print(f"{level}\t{message}")


def main():
    try:
        import tomllib
    except ImportError:
        emit("warning", "Codex config inspection skipped: Python 3.11+ with tomllib required")
        return

    repo = Path.cwd()
    try:
        with (repo / ".codex/config.toml").open("rb") as stream:
            config = tomllib.load(stream)
    except (OSError, ValueError):
        emit("warning", "Codex config inspection failed: unreadable file or invalid TOML")
        return

    features = config.get("features", {})
    if not isinstance(features, dict):
        emit("warning", "Codex features must be a TOML table")
        return
    hooks = features.get("hooks", features.get("codex_hooks"))
    if hooks is True:
        emit("info", "codex hooks enabled in local config (effective runtime policy not checked)")
    elif hooks is False:
        emit("warning", "codex hooks are disabled in local config")
    elif hooks is None:
        emit("warning", "codex hook flag is not configured locally; inherited settings not checked")
    else:
        emit("warning", "codex hook flag must be a boolean")

    skills = config.get("skills", {})
    entries = skills.get("config", []) if isinstance(skills, dict) else None
    if not isinstance(entries, list) or any(not isinstance(e, dict) for e in entries):
        emit("warning", "Codex skills.config must be an array of tables")
        return
    overrides = {}
    for entry in entries:
        raw = entry.get("path")
        enabled = entry.get("enabled", True)
        if not isinstance(raw, str) or not isinstance(enabled, bool):
            emit("warning", "Codex skill entry requires a path string and optional boolean enabled")
            continue
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = repo / path
        if path.name != "SKILL.md":
            path = path / "SKILL.md"
        overrides[path.resolve()] = enabled

    user_dir = Path.home()
    codex_dir = Path(os.environ.get("CODEX_HOME", user_dir / ".codex"))
    user_skills = Path(os.environ.get("CODEX_USER_SKILLS_DIR", user_dir / ".agents/skills"))
    roots = (repo / ".agents/skills", user_skills, codex_dir / "skills")
    for name in ("architecture-review", "security-review", "operational-risk-review"):
        source = (repo / "skills" / name / "SKILL.md").resolve()
        candidates = [source]
        for root in roots:
            candidates.extend(root / alias / "SKILL.md" for alias in (name, f"gene-devops-{name}"))
        has_disabled = any(overrides.get(p.resolve()) is False for p in candidates)
        if has_disabled:
            emit("info", f"codex skill explicitly disabled on at least one local path: {name}")
        if any(overrides.get(p.resolve()) is True and p.is_file() for p in candidates):
            emit("info", f"codex skill configured: {name}")
        elif any(p.is_file() and overrides.get(p.resolve()) is not False for p in candidates[1:]):
            emit("info", f"codex skill discovered: {name} (activation not checked)")
        elif not has_disabled:
            emit("warning", f"codex skill not configured or discovered: {name}")


if __name__ == "__main__":
    main()
