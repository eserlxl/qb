"""Aggregate telemetry series tests."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

TELEMETRY_PATH = SHARED_DIR / "scripts/telemetry.py"
AGGREGATE_PATH = SHARED_DIR / "scripts/telemetry_aggregate.py"


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class TelemetryAggregateTests(unittest.TestCase):
    def setUp(self) -> None:
        if not TELEMETRY_PATH.exists() or not AGGREGATE_PATH.exists():
            self.skipTest("telemetry aggregate module missing")
        self.telemetry = _load("qb_telemetry_under_test", TELEMETRY_PATH)
        self.aggregate = _load("qb_telemetry_aggregate_under_test", AGGREGATE_PATH)

    def _record(self, run_id: str, *, kept: bool = True) -> dict:
        outcome = "kept" if kept else "reverted"
        return self.telemetry.build_telemetry(
            run_id=run_id,
            autonomy_level="A2",
            findings=[{"severity": "P2", "category": "quality", "confidence": "medium"}],
            evidence=[{"outcome": outcome, "after_exit": 0}],
            cost={"wall_ms": 10, "iterations": 1, "tokens": 20},
        )

    def test_build_aggregate_reuses_per_run_metric_slices(self) -> None:
        first = self._record("run-1")
        second = self._record("run-2", kept=False)

        series = self.aggregate.build_aggregate([first, second])

        self.assertEqual(
            series["schema_version"],
            self.aggregate.AGGREGATE_TELEMETRY_SCHEMA_VERSION,
        )
        self.assertEqual(series["run_count"], 2)
        self.assertEqual([run["run_id"] for run in series["runs"]], ["run-1", "run-2"])
        for source, entry in zip((first, second), series["runs"]):
            self.assertEqual(entry["schema_version"], self.telemetry.TELEMETRY_SCHEMA_VERSION)
            self.assertEqual(entry["autonomy_level"], source["autonomy_level"])
            for key in self.aggregate.TELEMETRY_SLICES:
                self.assertEqual(entry[key], source[key])

    def test_append_or_update_preserves_order_and_replaces_duplicate_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / self.aggregate.AGGREGATE_TELEMETRY_FILENAME
            self.assertEqual(self.aggregate.read_aggregate(path), self.aggregate.build_aggregate([]))

            first = self._record("run-1")
            second = self._record("run-2")
            replacement = self._record("run-1", kept=False)

            self.aggregate.append_or_update(path, first)
            self.aggregate.append_or_update(path, second)
            updated = self.aggregate.append_or_update(path, replacement)
            reread = self.aggregate.read_aggregate(path)

        self.assertEqual(updated, reread)
        self.assertEqual(updated["run_count"], 2)
        self.assertEqual([run["run_id"] for run in updated["runs"]], ["run-1", "run-2"])
        self.assertEqual(updated["runs"][0]["action"]["fixes_reverted"], 1)
        self.assertEqual(updated["runs"][1]["action"]["fixes_kept"], 1)

    def test_append_or_update_redacts_persisted_fields(self) -> None:
        token = "sk-" + ("B" * 24)
        record = self._record("run-clean")
        record["run_id"] = f"run-{token}"
        record["cost"]["tokens"] = f"tokens-{token}"

        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / self.aggregate.AGGREGATE_TELEMETRY_FILENAME
            updated = self.aggregate.append_or_update(path, record)
            persisted = path.read_text(encoding="utf-8")

        self.assertNotIn(token, persisted)
        self.assertIn("<redacted>", persisted)
        self.assertEqual(updated["runs"][0]["run_id"], "run-<redacted>")
        self.assertEqual(updated["runs"][0]["cost"]["tokens"], "tokens-<redacted>")

    def test_read_aggregate_fails_closed_for_corrupt_or_wrong_version(self) -> None:
        empty = self.aggregate.build_aggregate([])
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / self.aggregate.AGGREGATE_TELEMETRY_FILENAME
            path.write_text("{not-json", encoding="utf-8")
            self.assertEqual(self.aggregate.read_aggregate(path), empty)

            path.write_text(
                json.dumps({"schema_version": 999, "runs": [self._record("old")]}),
                encoding="utf-8",
            )
            self.assertEqual(self.aggregate.read_aggregate(path), empty)


if __name__ == "__main__":
    unittest.main()
