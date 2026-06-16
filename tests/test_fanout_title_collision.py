"""Cross-phase title-collision coverage for QB's reduce validators."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR
from tests.test_fanout_degenerate_phase_counts import (
    build_planner_tree,
    metric,
    run_validator as run_docs_validator,
)

PLAN_VALIDATOR_PATH = SHARED_DIR / "scripts/validate_planwright_plan.py"


def plan_item(title: str, checked: bool = False) -> str:
    marker = "x" if checked else " "
    return "\n".join(
        [
            f"- [{marker}] {title}",
            "      Mode: improve",
            "      Rationale: Fixture rationale tied to the title-collision validator.",
            "      Evidence: README.md:1 provides the stable fixture surface.",
            "      Surfaces: README.md",
            "      Development: Update the README.md fixture surface.",
            "      Acceptance: The fixture plan remains structurally valid.",
            f"      Verification: python3 {PLAN_VALIDATOR_PATH.name} --root .",
        ]
    )


def write_plan(root: Path, items: list[str]) -> None:
    (root / "README.md").write_text("fixture surface\n", encoding="utf-8")
    qb = root / ".qb"
    qb.mkdir()
    (qb / "plan.md").write_text("\n\n".join(items) + "\n", encoding="utf-8")


def run_plan_validator(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(PLAN_VALIDATOR_PATH), "--root", str(root)],
        text=True,
        capture_output=True,
        check=False,
    )


class FanoutTitleCollisionTests(unittest.TestCase):
    def test_duplicate_pending_titles_fail_plan_validation(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write_plan(
                root,
                [
                    plan_item("Shared Collision Title"),
                    plan_item("Shared Collision Title"),
                ],
            )
            result = run_plan_validator(root)

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(
            "duplicate pending title: 'Shared Collision Title'",
            result.stdout,
        )

    def test_duplicate_checked_titles_do_not_fail_pending_title_rule(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write_plan(
                root,
                [
                    plan_item("Historical Collision Title", checked=True),
                    plan_item("Historical Collision Title", checked=True),
                    plan_item("Current Unique Title"),
                ],
            )
            result = run_plan_validator(root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("pending_item_count=1", result.stdout)
        self.assertNotIn("duplicate pending title", result.stdout)

    def test_step2_indexes_same_slug_across_phase_scoped_files(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build_planner_tree(root, phase_count=2, subplans_per_phase=1)
            result = run_docs_validator(root, "step2")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(metric(result.stdout, "main_phase_count"), "2")
        self.assertEqual(metric(result.stdout, "phase_folder_count"), "2")
        self.assertEqual(metric(result.stdout, "subplan_count"), "2")
        self.assertNotIn("duplicate_subplan_number=", result.stdout)
        self.assertNotIn("invalid_subplan_filename=", result.stdout)

    def test_reduce_dedup_backstop_fails_without_mutating_plan(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write_plan(
                root,
                [
                    plan_item("Reduce Must Dedup This Title"),
                    plan_item("Reduce Must Dedup This Title"),
                ],
            )
            plan_path = root / ".qb/plan.md"
            before = plan_path.read_text(encoding="utf-8")
            result = run_plan_validator(root)
            after = plan_path.read_text(encoding="utf-8")

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(
            "duplicate pending title: 'Reduce Must Dedup This Title'",
            result.stdout,
        )
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
