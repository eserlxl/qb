"""The validator's heading contract must match what the planner specs emit.

The read-only validator enforces an exact, ordered set of section headings for
each generated document. The shared planner specs are what instruct the model to
produce those headings. If either side is edited without the other, generated
docs silently start failing validation. This pins that contract so a drift is
caught in CI instead of in the field.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest

from tests.qb_monorepo import SHARED_DIR

VALIDATOR_PATH = SHARED_DIR / "scripts/validate_planner_docs.py"
PLANWRIGHT_VALIDATOR_PATH = SHARED_DIR / "scripts/validate_planwright_plan.py"
PLANNERS = SHARED_DIR / "planners"
EXPORT_SPEC = PLANNERS / "export-planner.md"

# (validator heading-list attribute, planner spec that must emit those headings)
CONTRACT = (
    ("STEP1_HEADINGS", "first-planner.md"),
    ("ASSESSMENT_HEADINGS", "assessment-planner.md"),
    ("INDEX_HEADINGS", "second-planner.md"),
    ("SUBPLAN_HEADINGS", "second-planner.md"),
    ("AUDIT_HEADINGS", "third-planner.md"),
)


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    # Register before exec so the validator's @dataclass type resolution
    # (which looks up sys.modules[cls.__module__]) succeeds.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_validator():
    return _load_module(VALIDATOR_PATH, "qb_validator_under_test")


class SpecValidatorContractTests(unittest.TestCase):
    def setUp(self) -> None:
        if not VALIDATOR_PATH.exists() or not PLANNERS.exists():
            self.skipTest("shared validator or planner specs not present")
        self.validator = _load_validator()

    def test_every_validator_heading_appears_in_its_planner_spec(self) -> None:
        for attr, spec_name in CONTRACT:
            spec_path = PLANNERS / spec_name
            with self.subTest(headings=attr, spec=spec_name):
                if not spec_path.exists():
                    self.skipTest(f"planner spec missing: {spec_path}")
                headings = getattr(self.validator, attr)
                self.assertTrue(headings, f"validator {attr} is empty")
                text = spec_path.read_text(encoding="utf-8")
                missing = [h for h in headings if h not in text]
                self.assertEqual(
                    missing,
                    [],
                    f"{spec_name} is missing validator {attr} headings: {missing}",
                )


class ExportSpecValidatorContractTests(unittest.TestCase):
    """The export spec must document the exact fields and modes its validator enforces.

    validate_planwright_plan.py is the structural gate for the Step 3.5 export
    (.qb/plan.md); export-planner.md is what instructs the model to produce that
    format. If either side drifts, generated plans silently start failing the gate.
    This pins the contract: every REQUIRED_FIELD (plus the optional New Surfaces) and
    every VALID_MODE the validator checks must appear verbatim in the export spec.
    """

    def setUp(self) -> None:
        if not PLANWRIGHT_VALIDATOR_PATH.exists() or not EXPORT_SPEC.exists():
            self.skipTest("planwright-plan validator or export-planner spec not present")
        self.validator = _load_module(
            PLANWRIGHT_VALIDATOR_PATH, "qb_planwright_validator_under_test")
        self.spec_text = EXPORT_SPEC.read_text(encoding="utf-8")

    def test_export_spec_documents_validator_fields(self) -> None:
        for field in tuple(self.validator.REQUIRED_FIELDS) + ("New Surfaces",):
            with self.subTest(field=field):
                self.assertIn(f"{field}:", self.spec_text,
                              f"export-planner.md does not document the '{field}:' field")

    def test_export_spec_documents_validator_modes(self) -> None:
        for mode in self.validator.VALID_MODES:
            with self.subTest(mode=mode):
                self.assertIn(mode, self.spec_text,
                              f"export-planner.md does not document the '{mode}' Mode")


if __name__ == "__main__":
    unittest.main()
