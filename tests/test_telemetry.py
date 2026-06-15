"""Phase 7.1 -- telemetry record + precision gate.

Pins: the versioned record shape (detection/action/cost/quality groups), the
precision estimate, the fix-safety flag, secret redaction, and the precision gate
mapping measured quality to the max autonomy level (fail-closed when no data).
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

MODULE_PATH = SHARED_DIR / "scripts/telemetry.py"


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _finding(category="secret", severity="P1", confidence="high"):
    return {"category": category, "severity": severity, "confidence": confidence}


class TelemetryTests(unittest.TestCase):
    def setUp(self) -> None:
        if not MODULE_PATH.exists():
            self.skipTest("telemetry missing")
        self.t = _load("qb_telemetry_under_test", MODULE_PATH)

    def test_record_shape_and_version(self) -> None:
        rec = self.t.build_telemetry(
            run_id="r1", autonomy_level="A2",
            findings=[_finding("secret", "P1"), _finding("quality", "P3", "medium")],
            evidence=[{"outcome": "kept", "after_exit": 0}, {"outcome": "reverted", "after_exit": 1}])
        self.assertEqual(rec["schema_version"], self.t.TELEMETRY_SCHEMA_VERSION)
        self.assertEqual(rec["detection"]["findings_total"], 2)
        self.assertEqual(rec["detection"]["by_severity"]["P1"], 1)
        self.assertEqual(rec["action"]["fixes_kept"], 1)
        self.assertEqual(rec["action"]["fixes_reverted"], 1)
        self.assertEqual(rec["cost"]["tokens"], self.t.UNMEASURED)

    def test_precision_estimate(self) -> None:
        self.assertEqual(self.t.precision_estimate(3, 1), 0.75)
        self.assertIsNone(self.t.precision_estimate(0, 0))

    def test_fix_safety_flag_detects_kept_not_green(self) -> None:
        ok = self.t.build_telemetry(run_id="r", autonomy_level="A2", findings=[],
                                    evidence=[{"outcome": "kept", "after_exit": 0}])
        self.assertTrue(ok["quality"]["fix_safety_ok"])
        bad = self.t.build_telemetry(run_id="r", autonomy_level="A2", findings=[],
                                     evidence=[{"outcome": "kept", "after_exit": 2}])
        self.assertFalse(bad["quality"]["fix_safety_ok"])

    def test_precision_gate_fail_closed_and_thresholded(self) -> None:
        # no fixes attempted => no data => no auto-apply (A1 max)
        none_rec = self.t.build_telemetry(run_id="r", autonomy_level="A2", findings=[], evidence=[])
        self.assertEqual(self.t.max_permitted_autonomy(none_rec), "A1")
        # high precision + fix-safety => A2 permitted
        good = self.t.build_telemetry(run_id="r", autonomy_level="A2", findings=[],
                                      evidence=[{"outcome": "kept", "after_exit": 0}] * 9
                                               + [{"outcome": "reverted", "after_exit": 1}])
        self.assertEqual(self.t.max_permitted_autonomy(good), "A2")
        # below floor => A1
        poor = self.t.build_telemetry(run_id="r", autonomy_level="A2", findings=[],
                                      evidence=[{"outcome": "kept", "after_exit": 0}]
                                               + [{"outcome": "reverted", "after_exit": 1}] * 9)
        self.assertEqual(self.t.max_permitted_autonomy(poor), "A1")

    def test_secret_redaction(self) -> None:
        token = "ghp_" + "A" * 30
        rec = self.t.build_telemetry(run_id=f"run-{token}", autonomy_level="A0", findings=[], evidence=[])
        self.assertNotIn(token, rec["run_id"])
        self.assertIn("<redacted>", rec["run_id"])


if __name__ == "__main__":
    unittest.main()
