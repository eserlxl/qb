"""Guard: bump-version.sh keeps BASELINE.md's version in lockstep.

BASELINE.md records the gate-of-record version, and
``tests/test_baseline_consistency.py`` asserts it equals the VERSION file
exactly. So the sanctioned bump path must refresh BASELINE on a version bump;
otherwise the next release would fail ``make check`` with no instruction to fix
it (which is the drift that left BASELINE on v0.14.1 long after the tree moved).

This exercises the dry-run path (writes nothing): a bump must *report* that it
would update BASELINE.md, which proves the rewrite is wired and that its regex
still matches BASELINE's real format. ``ALLOW_DIRTY=1`` lets the dry-run run
against a working tree that may be dirty (e.g. mid-change or in CI checkout).
Standard library only.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import unittest

from tests.qb_monorepo import REPO_ROOT

BUMP = REPO_ROOT / "scripts" / "bump-version.sh"
BASELINE = REPO_ROOT / "BASELINE.md"
VERSION = REPO_ROOT / "VERSION"


def _sha(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class BaselineBumpLockstepTests(unittest.TestCase):
    def setUp(self) -> None:
        if not BUMP.exists():
            self.skipTest("bump-version.sh missing")
        if not BASELINE.exists():
            self.skipTest("BASELINE.md missing")

    def _dry_run(self, bump: str) -> str:
        env = dict(os.environ, ALLOW_DIRTY="1")
        proc = subprocess.run(
            ["bash", str(BUMP), bump, "--dry-run"],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, f"dry-run failed: {proc.stderr}")
        return proc.stdout

    def test_dry_run_reports_baseline_update(self) -> None:
        current = VERSION.read_text(encoding="utf-8").strip()
        text = BASELINE.read_text(encoding="utf-8")
        self.assertIn(f"## Regression reference (v{current})", text)
        self.assertIn(f"| Version (`VERSION`) | `{current}` |", text)
        self.assertRegex(text, r"Expected test functions\s*\|\s*510\b")
        self.assertIn("Any deviation from the version, exit status, counts, or guard set above", text)
        out = self._dry_run("minor")
        self.assertIn(
            "BASELINE.md",
            out,
            "bump-version.sh --dry-run did not report a BASELINE.md update; "
            "the gate-of-record version would silently drift",
        )
        # Harden the lockstep: the report must name the NEW bumped version for
        # BASELINE, not merely mention the file. A bump that reported BASELINE.md
        # but wrote the wrong (or unchanged) version would still drift the gate of
        # record while passing the substring check above.
        major, minor, _patch = (int(part) for part in current.split("."))
        bumped = f"{major}.{minor + 1}.0"
        self.assertIn(
            f"BASELINE.md gate-of-record version -> {bumped}",
            out,
            "bump-version.sh --dry-run must report the new bumped version for "
            "BASELINE.md; reporting the file without the bumped version would let "
            "the gate-of-record version drift out of lockstep with VERSION",
        )

    def test_dry_run_writes_nothing(self) -> None:
        before = _sha(BASELINE)
        self._dry_run("minor")
        self.assertEqual(before, _sha(BASELINE), "dry-run must not modify BASELINE.md")


if __name__ == "__main__":
    sys.exit(unittest.main())
