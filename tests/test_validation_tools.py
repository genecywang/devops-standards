"""Regression tests for manifest selection and multi-file syntax checks."""
import os
import shutil
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: sample\n'


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.bin = self.base / 'bin'
        self.bin.mkdir()
        for tool in ('bash', 'find', 'dirname', 'grep', 'mktemp', 'rm'):
            (self.bin / tool).symlink_to(shutil.which(tool))
        self.env = dict(os.environ, PATH=str(self.bin))

    def write(self, name, content):
        path = self.base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def validate(self):
        return subprocess.run(['/bin/bash', str(ROOT / 'validations/kubernetes.sh')],
                              cwd=self.base, env=self.env, text=True, capture_output=True)

    def test_irrelevant_yaml_needs_no_validator(self):
        self.write('config.yaml', 'schema: spec-driven\n')
        self.write('docs/archive/old.yaml', MANIFEST)
        self.write('chart/Chart.yaml', 'apiVersion: v2\nname: example\n')
        self.write('chart/templates/resource.yaml', MANIFEST + '{{ template }}\n')
        result = self.validate()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('skipping', result.stdout)

    def test_actual_manifest_requires_validator(self):
        self.write('resource.yaml', MANIFEST)
        self.assertEqual(self.validate().returncode, 1)

    def test_validator_receives_space_filename_and_failure_propagates(self):
        self.write('resource with space.yaml', MANIFEST)
        tool = self.write('bin/kubeconform', '#!/bin/bash\nprintf "%s\\n" "$@"\nexit 7\n')
        tool.chmod(0o755)
        result = self.validate()
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertIn('./resource with space.yaml', result.stdout)

    def test_missing_kind_is_not_silently_skipped(self):
        self.write('broken.yaml', 'apiVersion: v1\nmetadata: {}\n')
        self.assertNotEqual(self.validate().returncode, 0)

    def test_search_failure_propagates(self):
        (self.bin / 'find').unlink()
        tool = self.write('bin/find', '#!/bin/bash\nexit 13\n')
        tool.chmod(0o755)
        self.assertNotEqual(self.validate().returncode, 0)

    def test_file_inspection_error_propagates(self):
        self.write('resource.yaml', MANIFEST)
        (self.bin / 'grep').unlink()
        tool = self.write('bin/grep', '#!/bin/bash\nexit 2\n')
        tool.chmod(0o755)
        self.assertEqual(self.validate().returncode, 2)

    def test_syntax_checks_second_file(self):
        first = self.write('first.sh', 'true\n')
        second = self.write('second.sh', 'if then\n')
        result = subprocess.run(['bash', str(ROOT / 'scripts/check-shell-syntax.sh'), str(first), str(second)],
                                text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()
