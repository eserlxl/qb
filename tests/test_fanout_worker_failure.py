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

    def test_malformed_only_phase_file_fails_step2(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build_planner_tree(root, phase_count=1, subplans_per_phase=1)
            phase_dir = root / ".qb/phase-1-plans"
            for path in phase_dir.glob("*.md"):
                path.unlink()
            (phase_dir / "worker-output.md").write_text(
                "# Worker Output\n\nThis is not a conforming QB sub-plan filename.\n",
                encoding="utf-8",
            )
            result = run_validator(root, "step2")

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("invalid_subplan_filename=.qb/phase-1-plans/worker-output.md", result.stdout)
        self.assertIn("subplan_count=0", result.stdout)
        self.assertIn("phase_has_no_subplans=.qb/phase-1-plans", result.stdout)

    def test_reduce_barrier_surfaces_missing_or_empty_phase(self) -> None:
        """The reduce barrier must fail when a worker produces no usable phase output."""
        cases = {
            "missing": "missing_phase_folder=.qb/phase-1-plans",
            "empty": "phase_has_no_subplans=.qb/phase-1-plans",
        }
        for case, expected in cases.items():
            with self.subTest(case=case), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                build_planner_tree(root, phase_count=1, subplans_per_phase=1)
                phase_dir = root / ".qb/phase-1-plans"
                if case == "missing":
                    shutil.rmtree(phase_dir)
                else:
                    for path in phase_dir.glob("*.md"):
                        path.unlink()
                result = run_validator(root, "step2")

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(expected, result.stdout)
            self.assertNotIn("planner_docs_validation=passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
