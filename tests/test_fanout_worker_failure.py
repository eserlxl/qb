"""Fail-closed coverage for missing or invalid fan-out worker output."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from tests.test_fanout_degenerate_phase_counts import build_planner_tree, run_validator


class FanoutWorkerFailureTests(unittest.TestCase):
    def test_missing_phase_folder_fails_step2(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build_planner_tree(root, phase_count=1, subplans_per_phase=1)
            shutil.rmtree(root / ".qb/phase-1-plans")
            result = run_validator(root, "step2")

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("missing_phase_folder=.qb/phase-1-plans", result.stdout)

    def test_empty_phase_folder_fails_step2(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build_planner_tree(root, phase_count=1, subplans_per_phase=1)
            for path in (root / ".qb/phase-1-plans").glob("*.md"):
                path.unlink()
            result = run_validator(root, "step2")

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("phase_folder_count=1", result.stdout)
        self.assertIn("subplan_count=0", result.stdout)
        self.assertIn("phase_has_no_subplans=.qb/phase-1-plans", result.stdout)


if __name__ == "__main__":
    unittest.main()
