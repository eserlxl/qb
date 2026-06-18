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

    def _series_for_dimension(self, dimension: str, values: list) -> dict:
        runs = []
        path = self.trends.DIMENSION_PATHS[dimension]
        for index, value in enumerate(values, start=1):
            run = {
                "run_id": f"r{index}",
                "quality": {
                    "precision_estimate": self.trends.UNMEASURED,
                    "fix_safety_ok": self.trends.UNMEASURED,
                    "false_positive_signals": self.trends.UNMEASURED,
                },
                "cost": {"wall_ms": self.trends.UNMEASURED, "tokens": self.trends.UNMEASURED},
            }
            section, key = path
            run[section][key] = value
            runs.append(run)
        return {"runs": runs}

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

    def test_direction_verdict_improving_for_higher_is_better_dimension(self) -> None:
        series = self._series_for_dimension("precision", [0.4, 0.9])
        self.assertEqual(self.trends.direction_verdict(series, "precision"), "improving")

    def test_direction_verdict_regressing_for_lower_is_better_dimension(self) -> None:
        series = self._series_for_dimension("cost", [10, 20])
        self.assertEqual(self.trends.direction_verdict(series, "cost"), "regressing")

    def test_direction_verdict_stable_when_window_edges_match(self) -> None:
        series = self._series_for_dimension("latency", [15, 15])
        self.assertEqual(self.trends.direction_verdict(series, "latency"), "stable")

    def test_direction_verdict_short_series_is_non_committal(self) -> None:
        series = self._series_for_dimension("precision", [0.8])
        self.assertEqual(self.trends.direction_verdict(series, "precision"), "insufficient-data")

    def test_direction_verdict_all_unmeasured_is_non_committal(self) -> None:
        series = self._series_for_dimension("precision", [self.trends.UNMEASURED, None])
        self.assertEqual(self.trends.direction_verdict(series, "precision"), "unmeasured")

    def test_render_and_emit_trend_artifacts_are_reproducible(self) -> None:
        series = self._series()
        json_a = self.trends.render_trend_json(series, window=2)
        json_b = self.trends.render_trend_json(series, window=2)
        summary_a = self.trends.render_trend_summary(series, window=2)
        summary_b = self.trends.render_trend_summary(series, window=2)

        self.assertEqual(json_a, json_b)
        self.assertEqual(summary_a, summary_b)
        self.assertIn('"schema_version": 1', json_a)
        self.assertIn("precision: verdict=insufficient-data latest=0.5", summary_a)

        with tempfile.TemporaryDirectory() as d:
            json_path = Path(d) / "trend.json"
            summary_path = Path(d) / "trend.txt"
            rendered = self.trends.emit_trend_artifacts(series, json_path, summary_path, window=2)
            self.assertEqual(json_path.read_text(encoding="utf-8"), rendered["json"])
            self.assertEqual(summary_path.read_text(encoding="utf-8"), rendered["summary"])

    def test_trend_report_covers_every_declared_dimension(self) -> None:
        report = self.trends.build_trend_report(self._series(), window=2)
        self.assertEqual(report["schema_version"], self.trends.TREND_REPORT_SCHEMA_VERSION)
        self.assertEqual(sorted(report["series"]), sorted(self.trends.DIMENSION_PATHS))
        self.assertEqual(sorted(report["verdicts"]), sorted(self.trends.DIMENSION_PATHS))
        valid_verdicts = {
            self.trends.VERDICT_IMPROVING,
            self.trends.VERDICT_STABLE,
            self.trends.VERDICT_REGRESSING,
            self.trends.VERDICT_INSUFFICIENT,
            self.trends.VERDICT_UNMEASURED,
        }
        self.assertTrue(set(report["verdicts"].values()) <= valid_verdicts)


if __name__ == "__main__":
    unittest.main()
