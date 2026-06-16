"""Degenerate phase-count coverage for QB planner document validation."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

VALIDATOR_PATH = SHARED_DIR / "scripts/validate_planner_docs.py"


def _load_validator():
    if "qb_fanout_phase_count_validator" in sys.modules:
        return sys.modules["qb_fanout_phase_count_validator"]
    spec = importlib.util.spec_from_file_location(
        "qb_fanout_phase_count_validator",
        VALIDATOR_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


VALIDATOR = _load_validator()


def _write_heading_document(
    path: Path,
    headings: list[str],
    bodies: dict[str, str] | None = None,
) -> None:
    bodies = bodies or {}
    lines: list[str] = []
    for index, heading in enumerate(headings, start=1):
        lines.extend(
            [
                heading,
                "",
                bodies.get(
                    heading,
                    f"Fixture content for section {index} is intentionally complete enough "
                    "for the planner document validator.",
                ),
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def _subplan_path(phase: int, subphase: int) -> str:
    return f".qb/phase-{phase}-plans/phase-{phase}.{subphase}-fixture-work.md"


def build_planner_tree(root: Path, phase_count: int, subplans_per_phase: int = 1) -> None:
    if phase_count < 0:
        raise ValueError("phase_count must be non-negative")
    if subplans_per_phase < 0:
        raise ValueError("subplans_per_phase must be non-negative")

    qb = root / ".qb"
    qb.mkdir()

    roadmap_rows = "\n".join(
        f"| {phase} | Exercise fan-out phase {phase}. |"
        for phase in range(1, phase_count + 1)
    )
    roadmap = (
        "| Phase | Summary |\n"
        "| --- | --- |\n"
        f"{roadmap_rows}"
        if roadmap_rows
        else "No roadmap phases are declared in this degenerate fixture."
    )
    _write_heading_document(
        qb / "main-planning.md",
        VALIDATOR.STEP1_HEADINGS,
        {VALIDATOR.ROADMAP_HEADING: roadmap},
    )

    refs = [
        _subplan_path(phase, subphase)
        for phase in range(1, phase_count + 1)
        for subphase in range(1, subplans_per_phase + 1)
    ]
    _write_heading_document(
        qb / "sub-planning-index.md",
        VALIDATOR.INDEX_HEADINGS,
        {
            "## 3. Phase and Sub-Plan Map": "\n".join(f"- {ref}" for ref in refs)
            or "No sub-plans are declared.",
            "## 4. Prioritized Elaboration Order": "\n".join(
                f"{index}. {ref}" for index, ref in enumerate(refs, start=1)
            )
            or "No sub-plans are scheduled.",
        },
    )

    for phase in range(1, phase_count + 1):
        phase_dir = qb / f"phase-{phase}-plans"
        phase_dir.mkdir()
        for subphase in range(1, subplans_per_phase + 1):
            subplan = phase_dir / f"phase-{phase}.{subphase}-fixture-work.md"
            subplan.write_text(
                "\n".join(
                    [
                        f"# Phase {phase}.{subphase} - Fixture Work",
                        "",
                        *(
                            line
                            for index, heading in enumerate(
                                VALIDATOR.SUBPLAN_HEADINGS,
                                start=1,
                            )
                            for line in (
                                heading,
                                "",
                                f"Fixture body {index} contains enough concrete planning "
                                "detail to satisfy structure and minimum-length checks.",
                                "",
                            )
                        ),
                    ]
                ),
                encoding="utf-8",
            )


def run_validator(root: Path, mode: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(VALIDATOR_PATH), "--root", str(root), "--mode", mode],
        text=True,
        capture_output=True,
        check=False,
    )


class FanoutDegenerateFixtureBuilderTests(unittest.TestCase):
    def test_builder_emits_zero_and_one_phase_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            zero_root = Path(d)
            build_planner_tree(zero_root, phase_count=0)
            self.assertTrue((zero_root / ".qb/main-planning.md").is_file())
            self.assertFalse((zero_root / ".qb/phase-1-plans").exists())

        with tempfile.TemporaryDirectory() as d:
            one_root = Path(d)
            build_planner_tree(one_root, phase_count=1, subplans_per_phase=1)
            self.assertTrue(
                (one_root / ".qb/phase-1-plans/phase-1.1-fixture-work.md").is_file()
            )
            result = run_validator(one_root, "step2")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class FanoutDegeneratePhaseBehaviorTests(unittest.TestCase):
    def test_zero_phase_fixture_fails_closed_for_step1_and_step2(self) -> None:
        for mode in ("step1", "step2"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                build_planner_tree(root, phase_count=0)
                result = run_validator(root, mode)

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("main_phase_count=0", result.stdout)
            self.assertIn(
                "main_plan_has_no_detected_phases=.qb/main-planning.md",
                result.stdout,
            )
            if mode == "step2":
                self.assertIn("phase_folder_count=0", result.stdout)
                self.assertNotIn("missing_phase_folder=.qb/phase-1-plans", result.stdout)

    def test_one_phase_fixture_passes_step2_with_no_phantom_phase(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build_planner_tree(root, phase_count=1, subplans_per_phase=1)
            result = run_validator(root, "step2")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("main_phase_count=1", result.stdout)
        self.assertIn("phase_folder_count=1", result.stdout)
        self.assertIn("subplan_count=1", result.stdout)
        self.assertNotIn("missing_phase_folder=", result.stdout)
        self.assertNotIn("subplan_numbering_gap=", result.stdout)
        self.assertNotIn("phase-2-plans", result.stdout)


if __name__ == "__main__":
    unittest.main()
