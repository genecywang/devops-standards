"""Black-box setup checks in disposable repositories; no real user config."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ("architecture-review", "security-review", "operational-risk-review")


class WorkflowCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        shutil.copytree(ROOT / "scripts", self.repo / "scripts")
        for name in SKILLS:
            path = self.repo / "skills" / name
            path.mkdir(parents=True)
            (path / "SKILL.md").write_text("fixture\n")
        for name in ("all", "terraform", "helm", "kubernetes", "iam"):
            path = self.repo / "validations" / f"{name}.sh"
            path.parent.mkdir(exist_ok=True)
            path.write_text('#!/bin/sh\necho unexpected-validation >> "$UNEXPECTED_TOOL_LOG"\nexit 7\n')
            path.chmod(0o755)
        self.user_dir = self.base / "user"
        self.user_dir.mkdir()
        bin_dir = self.base / "bin"
        bin_dir.mkdir()
        for name in ("node", "npm", "openspec"):
            path = bin_dir / name
            path.write_text('#!/bin/sh\necho unexpected >> "$UNEXPECTED_TOOL_LOG"\nexit 7\n')
            path.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.user_dir),
                        CODEX_HOME=str(self.user_dir / ".codex"),
                        UNEXPECTED_TOOL_LOG=str(self.base / "unexpected-tools"),
                        PATH=str(bin_dir) + os.pathsep + os.environ["PATH"])

    def config(self, feature_text, skills=True):
        path = self.repo / ".codex/config.toml"
        path.parent.mkdir(exist_ok=True)
        body = feature_text + "\n"
        if skills:
            for name in SKILLS:
                body += f'\n[[skills.config]]\npath = "skills/{name}"\nenabled = true\n'
        path.write_text(body)

    def check(self, *args):
        result = subprocess.run(["bash", "scripts/check-codex-workflow.sh", *args],
                                cwd=self.repo, env=self.env, text=True,
                                capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.base / "unexpected-tools").exists(), "unexpected legacy tool invocation")
        return result.stdout

    def test_current_hook_and_optional_bundle_absent_are_clean(self):
        self.config("[features]\nhooks = true")
        output = self.check()
        self.assertNotIn("Warnings:", output)
        self.assertIn("hooks enabled", output)
        self.assertEqual(self.check("--hook"), "")

    def test_legacy_hook_remains_compatible(self):
        self.config("[features]\ncodex_hooks = true")
        self.assertIn("hooks enabled", self.check())

    def test_current_false_overrides_legacy_true(self):
        self.config("[features]\nhooks = false\ncodex_hooks = true")
        output = self.check()
        self.assertIn("hooks are disabled", output)
        self.assertNotIn("hooks enabled", output)

    def test_comment_or_other_table_does_not_enable_hooks(self):
        self.config('# codex_hooks = true\n[other]\nhooks = true')
        self.assertIn("hook flag is not configured", self.check())

    def test_dotted_keys_and_comments_are_parsed(self):
        self.config('features.hooks=true # supported TOML')
        self.assertNotIn("Warnings:", self.check())

    def test_disabled_skill_is_not_reported_enabled(self):
        self.config("[features]\nhooks = true")
        path = self.repo / ".codex/config.toml"
        path.write_text(path.read_text().replace("enabled = true", "enabled = false"))
        output = self.check()
        self.assertIn("skill explicitly disabled", output)
        self.assertNotIn("skill configured:", output)

    def test_user_discovery_symlink_is_found_without_config_entry(self):
        self.config("[features]\nhooks = true", skills=False)
        folder = self.user_dir / ".agents/skills"
        folder.mkdir(parents=True)
        for name in SKILLS:
            (folder / f"gene-devops-{name}").symlink_to(self.repo / "skills" / name)
        self.assertNotIn("Warnings:", self.check())

    def test_optional_bundle_user_symlink_is_reported(self):
        self.config("[features]\nhooks = true")
        target = self.base / "bundle/using-superpowers"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("fixture\n")
        folder = self.user_dir / ".agents/skills"
        folder.mkdir(parents=True)
        (folder / "superpowers").symlink_to(target.parent)
        output = self.check()
        self.assertIn("optional Superpowers discovered", output)
        self.assertNotIn("Warnings:", output)

    def test_invalid_config_does_not_echo_values_and_hook_json_is_valid(self):
        marker = "PRIVATE_CONFIG_SENTINEL"
        self.config(f'[features]\nhooks = "{marker}')
        output = self.check()
        self.assertIn("invalid TOML", output)
        self.assertNotIn(marker, output)
        payload = json.loads(self.check("--hook"))
        self.assertEqual(payload["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertNotIn(marker, json.dumps(payload))

    def test_missing_config_is_reported(self):
        self.assertIn(".codex/config.toml is missing", self.check())

    def test_configured_missing_skill_is_not_reported_available(self):
        self.config("[features]\nhooks = true")
        (self.repo / "skills/security-review/SKILL.md").rename(
            self.repo / "skills/security-review/unused.md")
        result = subprocess.run(["bash", "scripts/check-codex-workflow.sh"],
                                cwd=self.repo, env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("skill not configured or discovered: security-review", result.stdout)
        self.assertNotIn("skill configured: security-review", result.stdout)
        payload = json.loads(self.check("--hook"))
        self.assertIn("repo skill missing", payload["hookSpecificOutput"]["additionalContext"])

    def test_wrong_config_types_do_not_leak_values(self):
        self.config('[features]\nhooks = "PRIVATE_VALUE"\n[skills]\nconfig = "PRIVATE_VALUE"',
                    skills=False)
        output = self.check()
        self.assertIn("hook flag must be a boolean", output)
        self.assertIn("skills.config must be an array", output)
        self.assertNotIn("PRIVATE_VALUE", output)

    def test_directory_and_skill_file_overrides_are_supported(self):
        self.config("[features]\nhooks = true")
        path = self.repo / ".codex/config.toml"
        path.write_text(path.read_text().replace('review"', 'review/SKILL.md"'))
        self.assertNotIn("Warnings:", self.check())

    def test_disabled_copy_does_not_hide_an_independent_discovered_copy(self):
        self.config("[features]\nhooks = true")
        path = self.repo / ".codex/config.toml"
        path.write_text(path.read_text().replace("enabled = true", "enabled = false"))
        folder = self.user_dir / ".agents/skills/security-review"
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text("independent fixture\n")
        output = self.check()
        self.assertIn("skill discovered: security-review", output)
        self.assertIn("skill explicitly disabled", output)

    def test_setup_has_no_node_npm_or_openspec_dependency(self):
        self.config("[features]\nhooks = true")
        self.assertFalse((self.repo / "openspec").exists())
        self.assertNotIn("Warnings:", self.check())
        self.assertEqual(self.check("--hook"), "")

    def test_bootstrap_creates_config_without_legacy_tools(self):
        self.config("[features]\nhooks = true")
        config = self.repo / ".codex/config.toml"
        example = config.with_name("config.example.toml")
        config.rename(example)
        result = subprocess.run(["bash", "scripts/bootstrap-codex-workflow.sh"],
                                cwd=self.repo, env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(config.read_text(), example.read_text())
        self.assertFalse((self.base / "unexpected-tools").exists())

    def test_bootstrap_preserves_existing_config(self):
        self.config("[features]\nhooks = false")
        config = self.repo / ".codex/config.toml"
        original = config.read_bytes()
        result = subprocess.run(["bash", "scripts/bootstrap-codex-workflow.sh"],
                                cwd=self.repo, env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(config.read_bytes(), original)
        self.assertFalse((self.base / "unexpected-tools").exists())

    def test_removed_install_flag_cannot_install_or_write_config(self):
        result = subprocess.run(["bash", "scripts/bootstrap-codex-workflow.sh", "--install-openspec"],
                                cwd=self.repo, env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.repo / ".codex/config.toml").exists())
        self.assertFalse((self.base / "unexpected-tools").exists())

    def test_hook_escapes_quotes_and_backslashes_in_later_lines(self):
        self.config("[features]\nhooks = true")
        # Source only helper definitions, before the main checker calls.
        definitions = (self.repo / "scripts/check-codex-workflow.sh").read_text().split('\ncheck_codex_config\n')[0]
        harness = self.repo / "serialize.sh"
        harness.write_text(definitions + '\nadd_warning \'second line "quoted" C:\\tmp\'\nprint_hook_report\n')
        result = subprocess.run(["bash", str(harness)], cwd=self.repo,
                                env=self.env, text=True, capture_output=True, check=True)
        payload = json.loads(result.stdout)
        self.assertIn('second line "quoted" C:\\tmp', payload["hookSpecificOutput"]["additionalContext"])


if __name__ == "__main__":
    unittest.main()
