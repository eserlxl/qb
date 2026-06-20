"""M7 readiness aggregator: fail-closed behavior + signal-set drift guard (Phase 6.3).

Proves the cross-phase aggregator (``shared/scripts/m7_readiness.py``) can only pass
when every signal is positively established, names any single false signal, and that
its signal set does not drift from ``production_gate.PRODUCTION_GATE_CHECKS`` or from
the Phase 6.1 readiness checklist / Phase 6.2 release-gating procedure that document it.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.qb_monorepo import REPO_ROOT, SHARED_DIR

SCRIPTS = SHARED_DIR / "scripts"


def _load(name: str, filename: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _conjuncts() -> tuple:
    return tuple(_load("qb_production_gate", "production_gate.py").PRODUCTION_GATE_CHECKS)


def _all_pass_decision() -> dict:
    signals = {name: True for name in _conjuncts()}
    return {"passed": True, "failures": [], "checks": dict(signals),
            "signals": signals, "permitted_autonomy": "A2"}


class M7ReadinessAggregatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.m7 = _load("qb_m7_readiness", "m7_readiness.py")
        self.conjuncts = _conjuncts()

    def test_all_signals_pass_yields_ready(self) -> None:
        with mock.patch.object(self.m7._signals, "gate_decision",
                               return_value=_all_pass_decision()):
            verdict = self.m7.evaluate("audit", "root")
        self.assertTrue(verdict["passed"])
        self.assertEqual(verdict["failures"], [])
        self.assertTrue(verdict["checks"]["autonomy_earned"])

    def test_each_single_false_signal_denies_and_is_named(self) -> None:
        for conjunct in self.conjuncts:
            decision = _all_pass_decision()
            decision["signals"][conjunct] = False
            with mock.patch.object(self.m7._signals, "gate_decision", return_value=decision):
                verdict = self.m7.evaluate("audit", "root")
            with self.subTest(conjunct=conjunct):
                self.assertFalse(verdict["passed"], f"{conjunct} false must deny readiness")
                self.assertIn(conjunct, verdict["failures"])

    def test_autonomy_not_earned_denies(self) -> None:
        decision = _all_pass_decision()
        decision["permitted_autonomy"] = "A1"  # below A2: Phase 3 autonomy not earned
        with mock.patch.object(self.m7._signals, "gate_decision", return_value=decision):
            verdict = self.m7.evaluate("audit", "root")
        self.assertFalse(verdict["passed"])
        self.assertIn("autonomy_earned", verdict["failures"])

    def test_crashed_assembly_fails_closed(self) -> None:
        with mock.patch.object(self.m7._signals, "gate_decision",
                               side_effect=RuntimeError("boom")):
            verdict = self.m7.evaluate("audit", "root")
        self.assertFalse(verdict["passed"])
        self.assertIn("production_gate_error", verdict["failures"])

    def test_missing_evidence_fails_closed(self) -> None:
        # A real run over an empty audit dir (no telemetry / recoverability record)
        # must not read ready -- the aggregator is fail-closed on absent evidence.
        with tempfile.TemporaryDirectory() as d:
            verdict = self.m7.evaluate(str(Path(d) / "audit"), d)
        self.assertFalse(verdict["passed"])

    def test_signal_set_matches_conjuncts_and_is_documented(self) -> None:
        # Drift guard: the signal set is exactly the six production-gate conjuncts plus
        # autonomy_earned, and every conjunct is named in the Phase 6.1 checklist
        # (BASELINE.md) and Phase 6.2 procedure (RUNBOOK.md) that document the gate.
        with mock.patch.object(self.m7._signals, "gate_decision",
                               return_value=_all_pass_decision()):
            checks = self.m7.evaluate("audit", "root")["checks"]
        self.assertEqual(set(checks), set(self.conjuncts) | {"autonomy_earned"})
        baseline = (REPO_ROOT / "BASELINE.md").read_text(encoding="utf-8")
        runbook = (REPO_ROOT / "RUNBOOK.md").read_text(encoding="utf-8")
        for conjunct in self.conjuncts:
            with self.subTest(conjunct=conjunct):
                self.assertIn(conjunct, baseline)
                self.assertIn(conjunct, runbook)


if __name__ == "__main__":
    unittest.main()
