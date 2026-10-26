"""Optional installer entry points, isolated from real user directories."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class InstallerSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.codex = self.base / "codex"
        self.claude = self.base / "claude"
        self.skills = self.base / "agents/skills"
        self.env = dict(os.environ, CODEX_HOME=str(self.codex),
                        CLAUDE_HOME=str(self.claude), CODEX_USER_SKILLS_DIR=str(self.skills))
        self.codex_link = self.skills / "gene-devops-install-skills"
        self.claude_link = self.claude / "skills/install-skills"

    def run_sync(self, *args, expected=0):
        result = subprocess.run(["bash", str(ROOT / "scripts/sync-personal-ai-config.sh"), *args],
                                env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_installer_is_not_installed_by_default(self):
        self.run_sync()
        self.assertFalse(self.codex_link.exists())
        self.assertFalse(self.claude_link.exists())

    def test_explicit_installer_for_both_clients_and_idempotency(self):
        self.run_sync("--with-installer")
        self.run_sync("--with-installer")
        for link in (self.codex_link, self.claude_link):
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), ROOT / "skills/install-skills")

    def test_codex_only_installer_independent_of_review_skills(self):
        self.run_sync("--codex-only", "--no-skills", "--with-installer")
        self.assertTrue(self.codex_link.is_symlink())
        self.assertFalse(self.claude.exists())
        self.assertFalse((self.codex / "skills").exists())

    def test_claude_only_installer(self):
        self.run_sync("--claude-only", "--with-installer")
        self.assertTrue(self.claude_link.is_symlink())
        self.assertFalse(self.codex.exists())
        self.assertFalse(self.skills.exists())

    def test_installer_dry_run_writes_nothing(self):
        result = self.run_sync("--with-installer", "--dry-run")
        self.assertIn(str(self.codex_link), result.stdout)
        self.assertIn(str(self.claude_link), result.stdout)
        self.assertEqual(list(self.base.iterdir()), [])

    def test_conflict_preserved_then_backed_up_with_force(self):
        self.skills.mkdir(parents=True)
        self.codex_link.write_text("existing installer\n")
        self.run_sync("--codex-only", "--with-installer", expected=1)
        self.assertFalse(self.codex.exists())
        self.assertEqual(self.codex_link.read_text(), "existing installer\n")
        self.run_sync("--codex-only", "--with-installer", "--force")
        self.assertEqual(self.codex_link.resolve(), ROOT / "skills/install-skills")
        backups = list((self.codex / "skill-backups").glob("gene-devops-install-skills.bak.*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), "existing installer\n")

    def test_late_global_conflict_does_not_write_codex(self):
        self.claude.mkdir()
        (self.claude / "CLAUDE.md").write_text("keep")
        self.run_sync(expected=1)
        self.assertFalse(self.codex.exists())
        self.assertFalse(self.skills.exists())

    def test_modern_links_and_readonly_check(self):
        self.run_sync("--with-installer")
        before = sorted(str(p) for p in self.base.rglob("*"))
        result = self.check_personal("--with-installer")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(before, sorted(str(p) for p in self.base.rglob("*")))
        link = self.skills / "gene-devops-security-review"
        link.unlink()
        link.symlink_to(self.base / "missing")
        self.assertEqual(self.check_personal().returncode, 1)

    def check_personal(self, *args):
        return subprocess.run(["python3", str(ROOT / "scripts/check-personal-ai-config.py"), *args],
                              env=self.env, capture_output=True, text=True)

    def test_migration_preserves_owned_links_outside_discovery(self):
        legacy = self.codex / "skills/gene-devops-security-review"
        legacy.parent.mkdir(parents=True)
        legacy.symlink_to(ROOT / "skills/security-review")
        self.run_sync()
        self.assertEqual(self.check_personal().returncode, 1)
        self.run_sync("--migrate-legacy-skills", "--dry-run")
        self.assertTrue(legacy.is_symlink())
        self.run_sync("--migrate-legacy-skills")
        self.assertFalse(legacy.is_symlink())
        backups = list((self.codex / "skill-backups").glob("*/gene-devops-security-review"))
        self.assertEqual(len(backups), 1)
        self.assertTrue(backups[0].is_symlink())
        self.assertEqual(self.check_personal().returncode, 0)

    def test_migration_refuses_foreign_link_before_writes(self):
        legacy = self.codex / "skills/gene-devops-security-review"
        legacy.parent.mkdir(parents=True)
        legacy.symlink_to(self.base / "foreign")
        self.run_sync("--migrate-legacy-skills", expected=1)
        self.assertFalse(self.skills.exists())
        self.assertFalse((self.codex / "AGENTS.md").exists())
        self.assertTrue(legacy.is_symlink())

    def test_migration_backup_parent_conflict_before_writes(self):
        legacy = self.codex / "skills/gene-devops-security-review"
        legacy.parent.mkdir(parents=True)
        legacy.symlink_to(ROOT / "skills/security-review")
        (self.codex / "skill-backups").write_text("keep")
        self.run_sync("--migrate-legacy-skills", expected=1)
        self.assertFalse(self.skills.exists())
        self.assertFalse((self.codex / "AGENTS.md").exists())

    def test_force_skill_backup_leaves_discovery(self):
        old = self.skills / "gene-devops-security-review"
        old.mkdir(parents=True)
        (old / "SKILL.md").write_text("---\nname: security-review\n---\nold")
        self.run_sync("--force")
        self.assertFalse(list(self.skills.glob("*.bak.*")))
        backups = list((self.codex / "skill-backups").glob("gene-devops-security-review.bak.*/SKILL.md"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(self.check_personal().returncode, 0)

    def test_checker_detects_old_named_backup(self):
        self.run_sync()
        old = self.skills / "renamed-copy"
        old.mkdir()
        (old / "SKILL.md").write_text("---\nname: security-review\n---\nold")
        self.assertEqual(self.check_personal().returncode, 1)

    def test_checker_handles_discovery_root_alias(self):
        legacy_root = self.codex / "skills"
        legacy_root.mkdir(parents=True)
        self.skills.parent.mkdir(parents=True)
        self.skills.symlink_to(legacy_root)
        self.run_sync()
        self.assertEqual(self.check_personal().returncode, 0)

    def test_claude_checker_ignores_unrequested_review_skills(self):
        self.run_sync("--claude-only", "--with-installer")
        other = self.claude / "skills/security-review"
        other.mkdir()
        (other / "SKILL.md").write_text("---\nname: security-review\n---\nclaude review")
        self.assertEqual(self.check_personal("--claude-only", "--with-installer").returncode, 0)

    def test_global_resources_readable_from_unrelated_cwd(self):
        self.run_sync("--with-installer")
        unrelated = self.base / "consumer"
        unrelated.mkdir()
        for home in (self.codex, self.claude):
            for name in ("workflows", "prompts", "validations"):
                self.assertEqual((home / "standards" / name).resolve(), ROOT / name)
            self.assertFalse((home / "standards/AGENTS.md").exists())
            result = subprocess.run(["cat", str(home / "standards/workflows/model-skill-evaluation.md")],
                                    cwd=unrelated, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Subagent Routing", result.stdout)
        result = subprocess.run(["python3", str(ROOT / "scripts/check-personal-ai-config.py"), "--with-installer"],
                                cwd=unrelated, env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_global_validation_dispatch_keeps_consumer_cwd(self):
        self.run_sync("--codex-only")
        consumer = self.base / "consumer"
        consumer.mkdir()
        result = subprocess.run(["bash", str(self.codex / "standards/validations/all.sh")],
                                cwd=consumer, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("terraform: no .tf files found", result.stdout)
        self.assertIn("iam: no JSON files found", result.stdout)
        # Poison child proves aggregate dispatch preserves cwd and propagates failure.
        fixture = self.base / "fixture"
        fixture.mkdir()
        (fixture / "all.sh").write_text((ROOT / "validations/all.sh").read_text())
        (fixture / "terraform.sh").write_text('pwd\nexit 17\n')
        result = subprocess.run(["bash", str(fixture / "all.sh")], cwd=consumer,
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 17)
        self.assertIn(str(consumer.resolve()), result.stdout)

    def test_resource_conflict_preflight_and_force_backup(self):
        target = self.codex / "standards/workflows"
        target.mkdir(parents=True)
        (target / "keep.txt").write_text("keep")
        self.run_sync(expected=1)
        self.assertFalse((self.codex / "AGENTS.md").exists())
        self.assertFalse(self.claude.exists())
        self.run_sync("--force")
        backups = list(target.parent.glob("workflows.bak.*/keep.txt"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), "keep")
        self.assertEqual(target.resolve(), ROOT / "workflows")

    def test_checker_detects_broken_resource_link(self):
        self.run_sync()
        link = self.codex / "standards/workflows"
        link.unlink()
        link.symlink_to(self.base / "missing")
        self.assertEqual(self.check_personal().returncode, 1)

    def test_conflicting_client_flags(self):
        self.run_sync("--codex-only", "--claude-only", expected=2)
        self.assertEqual(list(self.base.iterdir()), [])

    def test_invalid_parent_preflight(self):
        self.skills.parent.mkdir()
        self.skills.write_text("not a directory")
        self.run_sync(expected=1)
        self.assertFalse(self.codex.exists())


if __name__ == "__main__":
    unittest.main()
