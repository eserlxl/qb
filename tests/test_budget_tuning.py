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


def _run(rid, *, precision, fp_signals, fix_safety_ok=True, wall_ms=10, tokens=10):
    return {
        "schema_version": 1, "run_id": rid, "autonomy_level": "A2",
        "cost": {"wall_ms": wall_ms, "tokens": tokens},
        "quality": {"precision_estimate": precision, "fix_safety_ok": fix_safety_ok,
                    "false_positive_signals": fp_signals},
    }


def _agg(runs):
    return {"schema_version": 1, "runs": runs}


def _ceiling_report(trigger="max_fixes"):
    return budget.StopReport(trigger, 5, 5, 0, budget.BUDGET_STOP_EXIT)


class BudgetRecommenderTest(unittest.TestCase):
    def test_constraining_when_precision_and_fix_safety_hold(self):
        agg = _agg([
            _run("r1", precision=0.5, fp_signals=2),
            _run("r2", precision=0.7, fp_signals=2),
            _run("r3", precision=0.9, fp_signals=1),  # precision + quality improving
        ])
        rec = budget.recommend_budget(_ceiling_report("max_fixes"), agg)
        self.assertEqual(rec["advice"], budget.ADVICE_CONSTRAINING)
        self.assertEqual(rec["ceiling"], "max_fixes")
        self.assertEqual(rec["raise_path"], budget.raise_path("max_fixes"))

    def test_protecting_when_precision_regressing(self):
        agg = _agg([
            _run("r1", precision=0.9, fp_signals=1),
            _run("r2", precision=0.7, fp_signals=2),
            _run("r3", precision=0.5, fp_signals=3),  # precision regressing
        ])
        rec = budget.recommend_budget(_ceiling_report("max_fixes"), agg)
        self.assertEqual(rec["advice"], budget.ADVICE_PROTECTING)
        self.assertIsNone(rec["raise_path"])

    def test_insufficient_evidence_with_too_few_runs(self):
        agg = _agg([_run("r1", precision=0.9, fp_signals=1)])  # single run
        rec = budget.recommend_budget(_ceiling_report("max_fixes"), agg)
        self.assertEqual(rec["advice"], budget.ADVICE_INSUFFICIENT)
        self.assertIsNone(rec["raise_path"])

    def test_insufficient_evidence_when_precision_unmeasured(self):
        agg = _agg([
            _run("r1", precision=None, fp_signals=1),
            _run("r2", precision=None, fp_signals=1),
        ])
        rec = budget.recommend_budget(_ceiling_report("max_fixes"), agg)
        self.assertEqual(rec["advice"], budget.ADVICE_INSUFFICIENT)

    def test_non_ceiling_trigger_is_never_a_raise(self):
        agg = _agg([
            _run("r1", precision=0.8, fp_signals=1),
            _run("r2", precision=0.9, fp_signals=1),
        ])
        rec = budget.recommend_budget(_ceiling_report("completed"), agg)
        self.assertEqual(rec["advice"], budget.ADVICE_PROTECTING)
        self.assertIsNone(rec["ceiling"])
        self.assertIsNone(rec["raise_path"])


if __name__ == "__main__":
    unittest.main()
