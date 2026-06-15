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
PLANNERS = SHARED_DIR / "planners"

# (validator heading-list attribute, planner spec that must emit those headings)
CONTRACT = (
    ("STEP1_HEADINGS", "first-planner.md"),
    ("ASSESSMENT_HEADINGS", "assessment-planner.md"),
    ("INDEX_HEADINGS", "second-planner.md"),
    ("SUBPLAN_HEADINGS", "second-planner.md"),
    ("AUDIT_HEADINGS", "third-planner.md"),
)


def _load_validator():
    spec = importlib.util.spec_from_file_location("qb_validator_under_test", VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    # Register before exec so the validator's @dataclass type resolution
    # (which looks up sys.modules[cls.__module__]) succeeds.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


if __name__ == "__main__":
    unittest.main()
