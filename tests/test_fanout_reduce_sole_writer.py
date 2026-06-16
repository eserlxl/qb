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


def subplan_refs(root: Path) -> list[str]:
    qb = root / ".qb"
    return sorted(
        f".qb/{path.relative_to(qb).as_posix()}"
        for path in qb.glob("phase-*-plans/*.md")
    )


def write_single_reference_index(root: Path) -> None:
    refs = subplan_refs(root)
    bodies = {
        "## 3. Phase and Sub-Plan Map": "\n".join(f"- {ref}" for ref in refs),
        "## 4. Prioritized Elaboration Order": (
            "The reduce order is derived from the phase-qualified map above."
        ),
    }
    lines: list[str] = []
    for index, heading in enumerate(VALIDATOR.INDEX_HEADINGS, start=1):
        lines.extend(
            [
                heading,
                "",
                bodies.get(
                    heading,
                    f"Index fixture section {index} is complete enough for validation.",
                ),
                "",
            ]
        )
    (root / ".qb/sub-planning-index.md").write_text("\n".join(lines), encoding="utf-8")


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

    def test_index_references_each_subplan_exactly_once(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build_planner_tree(root, phase_count=2, subplans_per_phase=2)
            write_single_reference_index(root)
            expected_refs = subplan_refs(root)
            index_text = (root / ".qb/sub-planning-index.md").read_text(encoding="utf-8")
            result = run_validator(root, "step2")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        found_refs = [
            match.group(0)[2:] if match.group(0).startswith("./") else match.group(0)
            for match in VALIDATOR.INDEX_REF_RE.finditer(index_text)
        ]
        self.assertEqual(sorted(found_refs), expected_refs)
        for ref in expected_refs:
            self.assertEqual(found_refs.count(ref), 1, ref)

    def test_reduce_validator_output_is_idempotent(self) -> None:
        for mode in ("step2", "all"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                build_planner_tree(root, phase_count=2, subplans_per_phase=2)
                write_single_reference_index(root)
                write_audit(root)
                first = run_validator(root, mode)
                second = run_validator(root, mode)

            self.assertEqual(first.returncode, second.returncode)
            self.assertEqual(first.stdout, second.stdout)


if __name__ == "__main__":
    unittest.main()
