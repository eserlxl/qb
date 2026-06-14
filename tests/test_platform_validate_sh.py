"""Failure-path coverage for every platform's validate.sh CI gate.

The per-platform validate.sh scripts are otherwise only run against the healthy
repo, so their rejection branches are unverified. For each platform this copies
the package into a temp dir and confirms validate.sh actually fails on a missing
required file and on a mis-named manifest, not just that it passes when clean.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.qb_monorepo import CLAUDE_CODE, CODEX, CURSOR


def _run(tmp_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(tmp_root / "scripts/validate.sh")],
        text=True,
        capture_output=True,
        check=False,
    )


class _ValidateShFailureBase:
    """Rejection-branch checks parameterized by a tests.qb_monorepo descriptor.

    Concrete subclasses set ``PLATFORM`` and also inherit ``unittest.TestCase``
    so the shared ``test_*`` methods run once per platform. This mixin is not a
    TestCase itself, so it is never collected on its own.
    """

    PLATFORM: dict

    def setUp(self) -> None:
        src_root = self.PLATFORM["root"]
        if not (src_root / "scripts/validate.sh").exists():
            self.skipTest(f"{self.PLATFORM['id']} platform not built yet")
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name) / src_root.name
        shutil.copytree(src_root, self.root)
        # Manifest path inside the copy; host layouts differ, so derive it from
        # the descriptor rather than hard-coding a per-platform path here.
        self.manifest = self.root / self.PLATFORM["manifest"].relative_to(src_root)

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
        data = json.loads(self.manifest.read_text(encoding="utf-8"))
        data["name"] = f"not-{self.PLATFORM['id']}"
        self.manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")
        result = _run(self.root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("unexpected_plugin_name", result.stdout + result.stderr)


class ClaudeCodeValidateShFailureTests(_ValidateShFailureBase, unittest.TestCase):
    PLATFORM = CLAUDE_CODE


class CursorValidateShFailureTests(_ValidateShFailureBase, unittest.TestCase):
    PLATFORM = CURSOR


class CodexValidateShFailureTests(_ValidateShFailureBase, unittest.TestCase):
    PLATFORM = CODEX

    def test_planted_secret_fails(self) -> None:
        # Codex-only: its validate.sh is the repo's CI-time tracked-file secret
        # scanner. Build the token by concatenation so this source carries no
        # literal credential (and never trips a secret scan itself).
        fake_secret = "ghp_" + "A" * 32  # matches the github_legacy_pat pattern
        leak = self.root / "docs/USAGE.md"  # exists, passes checks 1-7
        leak.write_text(
            leak.read_text(encoding="utf-8") + f"\n{fake_secret}\n",
            encoding="utf-8",
        )
        result = _run(self.root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("tracked_secret_hygiene_failed", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
