"""Reduce sole-writer and no-dropped-phase artifact invariants."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.test_fanout_degenerate_phase_counts import (
    VALIDATOR,
    build_planner_tree,
    metric,
    run_validator,
)


def write_audit(root: Path) -> None:
    lines: list[str] = []
    for index, heading in enumerate(VALIDATOR.AUDIT_HEADINGS, start=1):
        lines.extend(
            [
                heading,
                "",
                f"Audit fixture section {index} is complete enough for heading validation.",
                "",
            ]
        )
    (root / ".qb/sub-planning-audit.md").write_text("\n".join(lines), encoding="utf-8")


class FanoutReduceSoleWriterTests(unittest.TestCase):
    def test_complete_enumeration_indexes_every_phase_once(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build_planner_tree(root, phase_count=3, subplans_per_phase=1)
            step2 = run_validator(root, "step2")
            write_audit(root)
            all_mode = run_validator(root, "all")

        self.assertEqual(step2.returncode, 0, step2.stdout + step2.stderr)
        self.assertEqual(metric(step2.stdout, "main_phase_count"), "3")
        self.assertEqual(metric(step2.stdout, "phase_folder_count"), "3")
        self.assertEqual(metric(step2.stdout, "subplan_count"), "3")
        self.assertNotIn("missing_phase_folder=", step2.stdout)
        self.assertNotIn("extra_phase_folder_without_main_phase=", step2.stdout)
        self.assertEqual(all_mode.returncode, 0, all_mode.stdout + all_mode.stderr)


if __name__ == "__main__":
    unittest.main()
