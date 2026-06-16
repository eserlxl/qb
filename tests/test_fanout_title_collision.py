"""Cross-phase title-collision coverage for QB's reduce validators."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

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


if __name__ == "__main__":
    unittest.main()
