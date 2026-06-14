"""Failure-path coverage for a platform's validate.sh CI gate.

The per-platform validate.sh scripts are otherwise only run against the healthy
repo, so their rejection branches are unverified. This copies the claude-code
package into a temp dir and confirms validate.sh actually fails on a missing
required file and on a mis-named manifest, not just that it passes when clean.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.qb_monorepo import CLAUDE_CODE

SRC_ROOT = CLAUDE_CODE["root"]


def _run(tmp_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(tmp_root / "scripts/validate.sh")],
        text=True,
        capture_output=True,
        check=False,
    )


class ClaudeCodeValidateShFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        if not (SRC_ROOT / "scripts/validate.sh").exists():
            self.skipTest("claude-code platform not built yet")
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name) / "claude-code"
        shutil.copytree(SRC_ROOT, self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_clean_copy_passes(self) -> None:
        result = _run(self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_required_file_fails(self) -> None:
        (self.root / "README.md").unlink()
        result = _run(self.root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("missing_required_file", result.stdout + result.stderr)

    def test_wrong_manifest_name_fails(self) -> None:
        manifest = self.root / ".claude-plugin/plugin.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["name"] = "not-claudeqb"
        manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")
        result = _run(self.root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("unexpected_plugin_name", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
