#!/usr/bin/env python3
"""Read-only verification of this checkout's personal configuration links."""
import argparse
import os
import re
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    clients = parser.add_mutually_exclusive_group()
    clients.add_argument('--codex-only', action='store_true')
    clients.add_argument('--claude-only', action='store_true')
    parser.add_argument('--with-installer', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    codex = Path(os.environ.get('CODEX_HOME', Path.home() / '.codex'))
    claude = Path(os.environ.get('CLAUDE_HOME', Path.home() / '.claude'))
    skills = Path(os.environ.get('CODEX_USER_SKILLS_DIR', Path.home() / '.agents/skills'))
    pairs = []
    legacy_entries = []
    if not args.claude_only:
        pairs.append((codex / 'AGENTS.md', root / 'templates/codex/AGENTS.global.md'))
        names = ['architecture-review', 'security-review', 'operational-risk-review']
        if args.with_installer:
            names.append('install-skills')
        for name in names:
            pairs.append((skills / f'gene-devops-{name}', root / 'skills' / name))
            for alias in (name, f'gene-devops-{name}'):
                legacy_entries.append((codex / 'skills' / alias, skills / f'gene-devops-{name}'))
                if alias == name:
                    legacy_entries.append((skills / alias, skills / f'gene-devops-{name}'))
    if not args.codex_only:
        pairs.append((claude / 'CLAUDE.md', root / 'templates/claude/CLAUDE.global.md'))
        if args.with_installer:
            pairs.append((claude / 'skills/install-skills', root / 'skills/install-skills'))
    failures = 0
    for destination, source in pairs:
        try:
            valid = destination.is_symlink() and destination.exists() and destination.resolve() == source.resolve()
        except (OSError, RuntimeError):
            valid = False
        if not valid:
            failures += 1
        print(f"{'ok' if valid else 'error'}: {destination}")
    for entry, destination in legacy_entries:
        if entry.parent.resolve() == destination.parent.resolve() and entry.name == destination.name:
            continue
        if entry.exists() or entry.is_symlink():
            print(f'error: legacy or duplicate skill entry: {entry}')
            failures += 1
    # Inspect immediate entries and nested bundles, including renamed backups.
    scan_roots = []
    if not args.claude_only:
        scan_roots.extend([(skills, {'architecture-review', 'security-review', 'operational-risk-review'} | ({'install-skills'} if args.with_installer else set())),
                           (codex / 'skills', {'architecture-review', 'security-review', 'operational-risk-review'} | ({'install-skills'} if args.with_installer else set()))])
    if not args.codex_only and args.with_installer:
        scan_roots.append((claude / 'skills', {'install-skills'}))
    def entry_identity(path):
        # Preserve distinct links to the same skill while collapsing directory aliases.
        return path.parent.resolve() / path.name

    expected = {entry_identity(destination) for destination, source in pairs}
    scanned = set()
    for scan_root, wanted in scan_roots:
        scan_key = (scan_root.resolve(), frozenset(wanted))
        if scan_key in scanned:
            continue
        scanned.add(scan_key)
        if not scan_root.is_dir():
            continue
        # Follow bundles such as Superpowers, but stop symlink cycles per ancestry.
        def inspect(directory, ancestors):
            nonlocal failures
            real = directory.resolve()
            if real in ancestors:
                return
            for entry in directory.iterdir():
                if not entry.is_dir():
                    continue
                metadata = entry / 'SKILL.md'
                if metadata.is_file():
                    content = metadata.read_text(encoding='utf-8')
                    frontmatter = content.split('---', 2)
                    match = re.search(r'^name:\s*[\"\']?([^\"\'\n]+?)[\"\']?\s*$', frontmatter[1], re.M) if len(frontmatter) == 3 and not frontmatter[0].strip() else None
                    if match and match.group(1).strip() in wanted and entry_identity(entry) not in expected:
                        print(f'error: duplicate skill metadata: {entry}')
                        failures += 1
                else:
                    inspect(entry, ancestors | {real})
        try:
            inspect(scan_root, set())
        except (OSError, RuntimeError, UnicodeError) as exc:
            print(f'error: cannot inspect skill directory: {scan_root} ({type(exc).__name__})')
            failures += 1
    print('Read-only inspection; runtime activation and configuration overrides are not verified.')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
