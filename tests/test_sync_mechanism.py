"""Behavioral tests for scripts/sync.sh: drift detection, restore, and CLI modes.

The top-level suite otherwise only asserts the *happy* path (`sync.sh --check`
exits 0 on the clean repo). These tests exercise the failure and recovery
behavior that the CI sync gate actually relies on, by materializing a throwaway
copy of the script + ``shared/`` source tree in a temp directory and driving it
end to end.
"""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.qb_monorepo import REPO_ROOT, SHARED_DIR

SYNC_SCRIPT = REPO_ROOT / "scripts/sync.sh"

# A destination that the sync MAP always materializes (Claude Code planner copy).
SAMPLE_DEST = "platforms/claude-code/skills/claudeqb-planner/planners/first-planner.md"


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(repo / "scripts/sync.sh"), *args],
        cwd=str(repo),
        text=True,
        capture_output=True,
        check=False,
    )


class SyncMechanismTests(unittest.TestCase):
    def setUp(self) -> None:
        if not SYNC_SCRIPT.exists() or not SHARED_DIR.exists():
            self.skipTest("sync.sh or shared/ not present")
        self._tmp = TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        (self.repo / "scripts").mkdir(parents=True)
        shutil.copy2(SYNC_SCRIPT, self.repo / "scripts/sync.sh")
        shutil.copytree(SHARED_DIR, self.repo / "shared")
        # Prime the throwaway repo so every mapped destination exists.
        primed = _run(self.repo)
        self.assertEqual(primed.returncode, 0, primed.stdout + primed.stderr)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_default_sync_creates_copies_and_check_passes(self) -> None:
        self.assertTrue((self.repo / SAMPLE_DEST).is_file())
        check = _run(self.repo, "--check")
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertIn("in sync", check.stdout)

    def test_check_detects_a_differing_copy(self) -> None:
        dest = self.repo / SAMPLE_DEST
        dest.write_text(dest.read_text(encoding="utf-8") + "\ndrift\n", encoding="utf-8")
        check = _run(self.repo, "--check")
        self.assertEqual(check.returncode, 1, check.stdout + check.stderr)
        self.assertIn("DIFFERS", check.stdout + check.stderr)

    def test_check_detects_a_missing_copy(self) -> None:
        (self.repo / SAMPLE_DEST).unlink()
        check = _run(self.repo, "--check")
        self.assertEqual(check.returncode, 1, check.stdout + check.stderr)
        self.assertIn("MISSING", check.stdout + check.stderr)

    def test_default_sync_restores_drift(self) -> None:
        dest = self.repo / SAMPLE_DEST
        dest.write_text("corrupted\n", encoding="utf-8")
        restore = _run(self.repo)
        self.assertEqual(restore.returncode, 0, restore.stdout + restore.stderr)
        self.assertEqual(
            dest.read_text(encoding="utf-8"),
            (self.repo / "shared/planners/first-planner.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(_run(self.repo, "--check").returncode, 0)

    def test_unknown_argument_exits_2(self) -> None:
        result = _run(self.repo, "frobnicate")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("unknown argument", result.stderr)

    def test_help_exits_zero_with_usage(self) -> None:
        result = _run(self.repo, "--help")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Usage", result.stdout)

    def test_missing_shared_source_fails(self) -> None:
        (self.repo / "shared/planners/first-planner.md").unlink()
        check = _run(self.repo, "--check")
        self.assertEqual(check.returncode, 1, check.stdout + check.stderr)
        self.assertIn("missing shared source", check.stderr)


if __name__ == "__main__":
    unittest.main()
