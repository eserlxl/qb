"""Phase 4.4 -- budget raise-path mapping + advisory recommender.

Pins: every budget ceiling that can halt a run maps to a documented raise-path
(evidence / step / guardrail) keyed on the StopReport.trigger, non-ceiling
triggers carry no raise-path, and each Budget ceiling field is named by some
raise-path step so the guidance stays tied to the engine.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import sys
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

BUDGET_PATH = SHARED_DIR / "scripts/budget.py"


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


budget = _load("qb_budget_tuning", BUDGET_PATH)

CEILING_TRIGGERS = ("max_findings", "max_fixes", "max_iterations",
                    "max_wall_time", "max_tokens")
NON_CEILING_TRIGGERS = ("completed", "kill")


class RaisePathMappingTest(unittest.TestCase):
    def test_every_ceiling_trigger_maps_to_a_complete_raise_path(self):
        for trigger in CEILING_TRIGGERS:
            path = budget.raise_path(trigger)
            self.assertIsNotNone(path, trigger)
            self.assertEqual(set(path), set(budget.RAISE_PATH_FIELDS), trigger)
            self.assertEqual(path["ceiling"], trigger)
            for field in ("evidence", "step", "guardrail"):
                self.assertTrue(path[field].strip(), f"{trigger}.{field} empty")

    def test_non_ceiling_triggers_have_no_raise_path(self):
        for trigger in NON_CEILING_TRIGGERS:
            self.assertIsNone(budget.raise_path(trigger), trigger)

    def test_mapping_covers_exactly_the_ceiling_triggers(self):
        self.assertEqual(set(budget.RAISE_PATHS), set(CEILING_TRIGGERS))

    def test_each_budget_ceiling_field_is_named_by_a_raise_step(self):
        # Ties the advisory mapping to the engine: every Budget ceiling field must
        # be referenced by some raise-path step, so a renamed ceiling cannot drift
        # silently away from its guidance.
        budget_fields = {f.name for f in dataclasses.fields(budget.Budget)}
        steps = " ".join(p["step"] for p in budget.RAISE_PATHS.values())
        for field in budget_fields:
            self.assertIn(field, steps, f"no raise-path step references Budget.{field}")


if __name__ == "__main__":
    unittest.main()
