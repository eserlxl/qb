"""Phase 7.1 -- telemetry record + precision gate.

Pins: the versioned record shape (detection/action/cost/quality groups), the
precision estimate, the fix-safety flag, secret redaction, and the precision gate
mapping measured quality to the max autonomy level (fail-closed when no data).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

MODULE_PATH = SHARED_DIR / "scripts/telemetry.py"
STORE_PATH = SHARED_DIR / "scripts/run_store.py"
BUDGET_PATH = SHARED_DIR / "scripts/budget.py"
POLICY_PATH = SHARED_DIR / "scripts/policy.py"
FIXER_PATH = SHARED_DIR / "scripts/fixer.py"


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


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def _init_accrual_repo(repo: Path) -> None:
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "QB Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "style.txt").write_text("messy\n", encoding="utf-8")
    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_style.py").write_text(
        "import pathlib, unittest\n"
        "class T(unittest.TestCase):\n"
        "    def test_clean(self):\n"
        "        self.assertEqual(pathlib.Path('style.txt').read_text().strip(), 'clean')\n",
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "fixture")


class _TwoRunAccrualFixture:
    def __init__(self, case: unittest.TestCase):
        self.case = case
        self.tmp = tempfile.TemporaryDirectory()
        case.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        _init_accrual_repo(self.repo)
        self.run1 = case.rs.RunStore(self.root / "run-1" / case.rs.OUTPUT_DIR_NAME).open()
        self.run2 = case.rs.RunStore(self.root / "run-2" / case.rs.OUTPUT_DIR_NAME).open()
        self._clock_values = iter((100.0, 100.25, 100.5, 100.75))

    def clock(self) -> float:
        return next(self._clock_values)

    def a2_eligible_telemetry(self, run_id: str) -> dict:
        return self.case.t.build_telemetry(
            run_id=run_id,
            autonomy_level="A2",
            findings=[_finding("quality", "P3", "medium")],
            evidence=[{"outcome": "kept", "after_exit": 0}] * 9
                     + [{"outcome": "reverted", "after_exit": 1}],
            cost={"wall_ms": 250, "iterations": 1, "tokens": 0},
        )

    def run_autofix(self, telemetry):
        budget = _load("qb_budget_for_telemetry_test", BUDGET_PATH)
        policy_mod = _load("qb_policy_for_telemetry_test", POLICY_PATH)
        fixer = _load("qb_fixer_for_telemetry_test", FIXER_PATH)
        policy = policy_mod.parse_policy({
            "autonomy_level": "A2",
            "auto_fixable_categories": ["quality"],
            "default_min_confidence": "medium",
            "write_allowlist": ["*.txt"],
        })
        finding = fixer.Finding(
            id=fixer.compute_finding_id("quality", "style.txt:1", "lint"),
            category="quality", severity="P3", confidence="medium",
            evidence="style.txt:1", rationale="x", suggested_fix="y",
            fix_strategy="autofix",
        )
        plan = fixer.plan_fix(finding, self.repo)
        results, report = budget.run_session(
            policy, self.repo, [(plan, lambda iso: iso.write_file("style.txt", "clean\n"))],
            telemetry=telemetry,
            clock=self.clock,
        )
        return results[0], report


class TelemetryTests(unittest.TestCase):
    def setUp(self) -> None:
        for path in (MODULE_PATH, STORE_PATH):
            if not path.exists():
                self.skipTest(f"missing module: {path}")
        self.t = _load("qb_telemetry_under_test", MODULE_PATH)
        self.rs = _load("qb_run_store_for_telemetry_test", STORE_PATH)

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

    @unittest.skipIf(subprocess.run(["git", "--version"], capture_output=True).returncode != 0, "git unavailable")
    def test_two_run_accrual_fixture_is_temp_and_deterministic(self) -> None:
        fixture = _TwoRunAccrualFixture(self)
        self.assertTrue(fixture.repo.is_relative_to(fixture.root))
        self.assertTrue(fixture.run1.root.is_relative_to(fixture.root))
        self.assertTrue(fixture.run2.root.is_relative_to(fixture.root))
        self.assertFalse((fixture.root / ".qb").exists())
        self.assertEqual(fixture.clock(), 100.0)
        self.assertEqual(fixture.clock(), 100.25)

        record = fixture.a2_eligible_telemetry("run-1")
        fixture.run1.write_telemetry(record)
        self.assertEqual(self.rs.load_prior_telemetry(fixture.run1.root), record)

    @unittest.skipIf(subprocess.run(["git", "--version"], capture_output=True).returncode != 0, "git unavailable")
    def test_run1_cold_start_clamps_a2_and_writes_a2_eligible_record(self) -> None:
        fixture = _TwoRunAccrualFixture(self)
        self.assertEqual(fixture.run1.read_telemetry(), {})

        result, _report = fixture.run_autofix(fixture.run1.read_telemetry())
        self.assertEqual(result["declared_level"], "A2")
        self.assertEqual(result["earned_ceiling"], "A1")
        self.assertEqual(result["level"], "A1")
        self.assertEqual(result["promoted"], [])
        self.assertEqual((fixture.repo / "style.txt").read_text(encoding="utf-8"), "messy\n")

        record = fixture.a2_eligible_telemetry("run-1")
        self.assertEqual(self.t.max_permitted_autonomy(record), "A2")
        fixture.run1.write_telemetry(record)
        self.assertEqual(fixture.run1.read_telemetry(), record)

    @unittest.skipIf(subprocess.run(["git", "--version"], capture_output=True).returncode != 0, "git unavailable")
    def test_run2_loads_earned_telemetry_and_promotes_verified_fix(self) -> None:
        fixture = _TwoRunAccrualFixture(self)
        fixture.run1.write_telemetry(fixture.a2_eligible_telemetry("run-1"))
        prior = self.rs.load_prior_telemetry(fixture.run1.root)

        result, _report = fixture.run_autofix(prior)
        self.assertEqual(result["declared_level"], "A2")
        self.assertEqual(result["earned_ceiling"], "A2")
        self.assertEqual(result["level"], "A2")
        self.assertEqual(result["promoted"], ["style.txt"])
        self.assertEqual((fixture.repo / "style.txt").read_text(encoding="utf-8"), "clean\n")


if __name__ == "__main__":
    unittest.main()
