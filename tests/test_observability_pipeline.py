"""Phase 4.5 -- end-to-end observability pipeline.

Spans the full multi-run pipeline over a fixture: build per-run telemetry
(telemetry.build_telemetry) -> append to the aggregate series
(telemetry_aggregate) -> compute trend verdicts (telemetry_trends) -> produce
advisory budget guidance (budget.recommend_budget). Asserts the documented
artifact and fields exist and that the trend artifact is byte-deterministic. No
single unit test spans these four modules together, so this guards their
integration contract.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

SCRIPTS = SHARED_DIR / "scripts"


def _load(name: str, filename: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class ObservabilityPipelineTest(unittest.TestCase):
    def setUp(self):
        # Canonical sibling names so the modules share one instance with budget.py's
        # own internal _load_sibling registrations.
        self.t = _load("qb_telemetry", "telemetry.py")
        self.agg = _load("qb_telemetry_aggregate", "telemetry_aggregate.py")
        self.trends = _load("qb_telemetry_trends", "telemetry_trends.py")
        self.budget = _load("qb_budget", "budget.py")

    def _record(self, run_id, kept, reverted, *, wall_ms, tokens):
        evidence = ([{"outcome": "kept", "after_exit": 0}] * kept
                    + [{"outcome": "reverted", "after_exit": 1}] * reverted)
        return self.t.build_telemetry(
            run_id=run_id, autonomy_level="A2",
            findings=[{"category": "quality", "severity": "P3", "confidence": "medium"}],
            evidence=evidence,
            cost={"wall_ms": wall_ms, "iterations": 1, "tokens": tokens})

    def test_per_run_telemetry_to_aggregate_to_trends_to_recommendation(self):
        with tempfile.TemporaryDirectory() as d:
            agg_path = Path(d) / self.agg.AGGREGATE_TELEMETRY_FILENAME

            # Two runs: precision improving (0.5 -> 0.9), latency/cost falling,
            # fix-safety held -- a run whose ceiling is legitimately constraining.
            self.agg.append_or_update(agg_path, self._record("r1", 1, 1, wall_ms=20, tokens=40))
            self.agg.append_or_update(agg_path, self._record("r2", 9, 1, wall_ms=10, tokens=20))

            # Documented artifact exists with the ordered series.
            self.assertTrue(agg_path.is_file())
            series = self.agg.read_aggregate(agg_path)
            self.assertEqual([run["run_id"] for run in series["runs"]], ["r1", "r2"])

            # Trend verdicts over the series.
            report = self.trends.build_trend_report(series)
            self.assertEqual(report["verdicts"]["precision"], self.trends.VERDICT_IMPROVING)
            self.assertEqual(report["verdicts"]["fix_safety"], self.trends.VERDICT_STABLE)

            # Advisory budget guidance from the same series.
            stop = self.budget.StopReport("max_fixes", 5, 5, 0, self.budget.BUDGET_STOP_EXIT)
            advice = self.budget.recommend_budget(stop, series)
            self.assertEqual(advice["advice"], self.budget.ADVICE_CONSTRAINING)
            self.assertEqual(advice["ceiling"], "max_fixes")
            self.assertEqual(advice["raise_path"], self.budget.raise_path("max_fixes"))

            # The trend artifact is byte-deterministic over an unchanged series.
            self.assertEqual(self.trends.render_trend_json(series),
                             self.trends.render_trend_json(series))


if __name__ == "__main__":
    unittest.main()
