"""Telemetry trend extractor tests."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

AGGREGATE_PATH = SHARED_DIR / "scripts/telemetry_aggregate.py"
TRENDS_PATH = SHARED_DIR / "scripts/telemetry_trends.py"


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class TelemetryTrendTests(unittest.TestCase):
    def setUp(self) -> None:
        if not AGGREGATE_PATH.exists() or not TRENDS_PATH.exists():
            self.skipTest("telemetry trend modules missing")
        self.aggregate = _load("qb_telemetry_aggregate_trend_test", AGGREGATE_PATH)
        self.trends = _load("qb_telemetry_trends_under_test", TRENDS_PATH)

    def _series(self) -> dict:
        return self.aggregate.build_aggregate([
            {
                "schema_version": 1,
                "run_id": "r1",
                "autonomy_level": "A1",
                "clamp_reason": None,
                "detection": {"findings_total": 3},
                "action": {"fixes_attempted": 0},
                "cost": {"wall_ms": self.trends.UNMEASURED, "tokens": self.trends.UNMEASURED},
                "quality": {
                    "precision_estimate": None,
                    "fix_safety_ok": False,
                    "false_positive_signals": self.trends.UNMEASURED,
                },
            },
            {
                "schema_version": 1,
                "run_id": "r2",
                "autonomy_level": "A2",
                "clamp_reason": None,
                "detection": {"findings_total": 1},
                "action": {"fixes_attempted": 2},
                "cost": {"wall_ms": 120, "tokens": 42},
                "quality": {
                    "precision_estimate": 0.5,
                    "fix_safety_ok": True,
                    "false_positive_signals": 1,
                },
            },
        ])

    def test_extract_series_preserves_unmeasured_and_none(self) -> None:
        series = self.trends.extract_series(self._series())

        self.assertEqual(
            series["precision"],
            [{"run_id": "r1", "value": None}, {"run_id": "r2", "value": 0.5}],
        )
        self.assertEqual(
            series["fix_safety"],
            [{"run_id": "r1", "value": False}, {"run_id": "r2", "value": True}],
        )
        self.assertEqual(series["latency"][0]["value"], self.trends.UNMEASURED)
        self.assertEqual(series["cost"][0]["value"], self.trends.UNMEASURED)
        self.assertEqual(series["quality"][0]["value"], self.trends.UNMEASURED)

    def test_dimension_series_reads_aggregate_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / self.aggregate.AGGREGATE_TELEMETRY_FILENAME
            self.aggregate.append_or_update(path, self._series()["runs"][0])
            self.aggregate.append_or_update(path, self._series()["runs"][1])
            precision = self.trends.dimension_series(path, "precision")

        self.assertEqual(
            precision,
            [{"run_id": "r1", "value": None}, {"run_id": "r2", "value": 0.5}],
        )


if __name__ == "__main__":
    unittest.main()
