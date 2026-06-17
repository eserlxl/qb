"""Phase 4.3 -- BudgetMeter -> telemetry cost mapping.

Pins ``budget.telemetry_cost``: a BudgetMeter's elapsed monotonic seconds map
to ``wall_ms`` through a single ``* 1000`` conversion (rounded to whole
milliseconds), while ``iterations`` and ``tokens`` carry the meter's counters
verbatim. The cost dict's keys are exactly the fields ``telemetry.build_telemetry``
consumes, so the mapped record is consumable without translation.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tests.qb_monorepo import SHARED_DIR

BUDGET_PATH = SHARED_DIR / "scripts/budget.py"
TELEMETRY_PATH = SHARED_DIR / "scripts/telemetry.py"


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


budget = _load("qb_budget", BUDGET_PATH)
telemetry = _load("qb_telemetry", TELEMETRY_PATH)


class _FakeClock:
    """Deterministic monotonic clock: the first read (meter construction) is the
    start instant; every later read returns a fixed ``now`` so ``elapsed()`` is
    a stable, call-count-independent delta."""

    def __init__(self, start: float, now: float) -> None:
        self._start = start
        self._now = now
        self._first = True

    def __call__(self) -> float:
        if self._first:
            self._first = False
            return self._start
        return self._now


def _meter(start: float, now: float):
    return budget.BudgetMeter(budget.Budget(), clock=_FakeClock(start, now))


class TelemetryCostMappingTest(unittest.TestCase):
    def test_maps_meter_fields_with_single_ms_conversion(self):
        meter = _meter(100.0, 102.5)  # 2.5s elapsed
        meter.iterations = 7
        meter.add_tokens(1234)

        cost = budget.telemetry_cost(meter)

        self.assertEqual(set(cost), {"wall_ms", "iterations", "tokens"})
        self.assertEqual(cost["wall_ms"], 2500)
        self.assertEqual(cost["iterations"], 7)
        self.assertEqual(cost["tokens"], 1234)

    def test_wall_ms_is_seconds_times_1000_rounded(self):
        # 0.0037s -> 3.7ms -> rounds to 4 (truncation would give 3), proving the
        # conversion rounds to whole milliseconds rather than truncating.
        meter = _meter(0.0, 0.0037)
        self.assertEqual(budget.telemetry_cost(meter)["wall_ms"], 4)

    def test_zero_elapsed_is_zero_wall_ms(self):
        meter = _meter(50.0, 50.0)
        self.assertEqual(budget.telemetry_cost(meter)["wall_ms"], 0)

    def test_keys_match_build_telemetry_cost_fields(self):
        # The mapped dict is consumable by build_telemetry's cost slice: exactly
        # the wall_ms / iterations / tokens fields, no extras.
        meter = _meter(0.0, 1.0)
        meter.iterations = 3
        meter.add_tokens(42)
        cost = budget.telemetry_cost(meter)
        self.assertEqual(cost, {"wall_ms": 1000, "iterations": 3, "tokens": 42})


class RunSessionCostWiringTest(unittest.TestCase):
    """run_session builds a finale telemetry record whose ``cost`` block carries the
    BudgetMeter's real wall_ms/iterations, never the UNMEASURED sentinel."""

    @staticmethod
    def _fix_plan():
        finding = SimpleNamespace(category="quality", severity="P3",
                                  confidence="low", evidence="x.py:1")
        return SimpleNamespace(finding=finding)

    def test_finale_telemetry_carries_real_metered_cost(self):
        # A0 (report-only) so run_finding short-circuits before isolation/git.
        policy = SimpleNamespace(autonomy_level="A0")
        items = [(self._fix_plan(), lambda: None) for _ in range(3)]
        clock = _FakeClock(1000.0, 1000.05)  # 0.05s elapsed -> 50 wall_ms

        with tempfile.TemporaryDirectory() as repo:
            _results, report = budget.run_session(policy, repo, items, clock=clock)

        self.assertEqual(report.trigger, "completed")
        self.assertIsNotNone(report.telemetry)
        cost = report.telemetry["cost"]
        self.assertEqual(cost["wall_ms"], 50)
        self.assertEqual(cost["iterations"], 3)
        # Real measured values flow through -- never the UNMEASURED sentinel.
        self.assertNotEqual(cost["wall_ms"], telemetry.UNMEASURED)
        self.assertNotEqual(cost["iterations"], telemetry.UNMEASURED)
        self.assertIsInstance(cost["wall_ms"], int)
        self.assertIsInstance(cost["iterations"], int)


if __name__ == "__main__":
    unittest.main()
