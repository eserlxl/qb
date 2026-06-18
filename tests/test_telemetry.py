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
GATE_PATH = SHARED_DIR / "scripts/release_gate.py"
BUDGET_PATH = SHARED_DIR / "scripts/budget.py"
POLICY_PATH = SHARED_DIR / "scripts/policy.py"
FIXER_PATH = SHARED_DIR / "scripts/fixer.py"

ACCRUAL_FIXTURE_ISOLATION_CHECKLIST = {
    "temp-root-only": "repo and run stores are created under tempfile.TemporaryDirectory",
    "deterministic-clock": "budget.run_session receives the fixture clock= callable",
    "no-live-qb": "fixture paths never point at the host .qb/ directory",
    "proxy-caveat": "deterministic fixture is a live-readiness proxy; true accrual depends on successive operator runs",
}


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
        self.clock_reads = []

    def clock(self) -> float:
        # Deterministic, unbounded monotonic clock: the Nth read is 100.0 + 0.25*N.
        # The sequence is stable regardless of how many reads a run makes, so it does
        # not break when run_session reads the clock at meter init, each ceiling check,
        # and the run-finale telemetry build (Phase 4.3).
        value = 100.0 + 0.25 * len(self.clock_reads)
        self.clock_reads.append(value)
        return value

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

    def test_record_schema_keys_are_stable(self) -> None:
        rec = self.t.build_telemetry(run_id="r1", autonomy_level="A2", findings=[], evidence=[])
        self.assertEqual(
            set(rec),
            {
                "schema_version", "run_id", "autonomy_level", "clamp_reason",
                "detection", "action", "cost", "quality",
            },
        )
        self.assertEqual(
            set(rec["detection"]),
            {"findings_total", "by_severity", "by_category", "confidence_histogram"},
        )
        self.assertEqual(
            set(rec["action"]),
            {"fixes_attempted", "fixes_kept", "fixes_reverted", "fixes_blocked"},
        )
        self.assertEqual(set(rec["cost"]), {"wall_ms", "iterations", "tokens"})
        self.assertEqual(
            set(rec["quality"]),
            {"precision_estimate", "false_positive_signals", "fix_safety_ok"},
        )

    def test_unset_tokens_stays_unmeasured_with_real_other_cost(self) -> None:
        # Real wall_ms/iterations are supplied but tokens is omitted: tokens must
        # remain UNMEASURED (never coerced to a measured 0) while the supplied cost
        # fields flow through unchanged.
        rec = self.t.build_telemetry(
            run_id="r", autonomy_level="A2", findings=[], evidence=[],
            cost={"wall_ms": 1500, "iterations": 5})
        self.assertEqual(rec["cost"]["wall_ms"], 1500)
        self.assertEqual(rec["cost"]["iterations"], 5)
        self.assertEqual(rec["cost"]["tokens"], self.t.UNMEASURED)
        self.assertNotEqual(rec["cost"]["tokens"], 0)
        # A supplied tokens value (including a real 0) is preserved, not overwritten.
        supplied = self.t.build_telemetry(
            run_id="r", autonomy_level="A2", findings=[], evidence=[],
            cost={"wall_ms": 1500, "iterations": 5, "tokens": 0})
        self.assertEqual(supplied["cost"]["tokens"], 0)

    def test_release_gate_and_telemetry_authorization_agree(self) -> None:
        # Phase 7.2: there must be ONE autonomy decision. release_gate.permitted_autonomy
        # and telemetry.max_permitted_autonomy mirror the same gate logic, so they must
        # return the identical level on the same record -- proven across the three
        # classes the gate distinguishes (passing, below-floor, fix-safety breach).
        rg = _load("qb_release_gate_for_telemetry_test", GATE_PATH)
        passing = self.t.build_telemetry(
            run_id="pass", autonomy_level="A2", findings=[],
            evidence=[{"outcome": "kept", "after_exit": 0}] * 9
                     + [{"outcome": "reverted", "after_exit": 1}])
        below = self.t.build_telemetry(
            run_id="below", autonomy_level="A2", findings=[],
            evidence=[{"outcome": "kept", "after_exit": 0}]
                     + [{"outcome": "reverted", "after_exit": 1}] * 9)
        breach = self.t.build_telemetry(
            run_id="breach", autonomy_level="A2", findings=[],
            evidence=[{"outcome": "kept", "after_exit": 0}] * 8
                     + [{"outcome": "kept", "after_exit": 3}])
        self.assertEqual(rg.permitted_autonomy(passing), "A2")
        self.assertEqual(rg.permitted_autonomy(below), "A1")
        self.assertEqual(rg.permitted_autonomy(breach), "A1")
        for rec in (passing, below, breach):
            self.assertEqual(
                rg.permitted_autonomy(rec), self.t.max_permitted_autonomy(rec),
                f"release-gate vs telemetry autonomy diverged on {rec['run_id']}")

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

    @unittest.skipIf(subprocess.run(["git", "--version"], capture_output=True).returncode != 0, "git unavailable")
    def test_run2_poor_or_breached_telemetry_stays_a1(self) -> None:
        poor_precision = self.t.build_telemetry(
            run_id="poor",
            autonomy_level="A2",
            findings=[_finding("quality", "P3", "medium")],
            evidence=[{"outcome": "kept", "after_exit": 0}]
                     + [{"outcome": "reverted", "after_exit": 1}] * 9,
        )
        breached_safety = self.t.build_telemetry(
            run_id="breach",
            autonomy_level="A2",
            findings=[_finding("quality", "P3", "medium")],
            evidence=[{"outcome": "kept", "after_exit": 2}],
        )

        for record in (poor_precision, breached_safety):
            fixture = _TwoRunAccrualFixture(self)
            fixture.run1.write_telemetry(record)
            prior = self.rs.load_prior_telemetry(fixture.run1.root)

            result, _report = fixture.run_autofix(prior)
            self.assertEqual(result["declared_level"], "A2", record["run_id"])
            self.assertEqual(result["earned_ceiling"], "A1", record["run_id"])
            self.assertEqual(result["level"], "A1", record["run_id"])
            self.assertEqual(result["promoted"], [], record["run_id"])
            self.assertEqual((fixture.repo / "style.txt").read_text(encoding="utf-8"), "messy\n")

    def _two_run_accrual_outcome(self) -> dict:
        fixture = _TwoRunAccrualFixture(self)
        run1, report1 = fixture.run_autofix(fixture.run1.read_telemetry())
        fixture.run1.write_telemetry(fixture.a2_eligible_telemetry("run-1"))
        run2, report2 = fixture.run_autofix(self.rs.load_prior_telemetry(fixture.run1.root))

        def stable(result):
            return {
                "declared_level": result["declared_level"],
                "earned_ceiling": result["earned_ceiling"],
                "level": result["level"],
                "outcome": result["outcome"],
                "promoted": result["promoted"],
                "changeset": result["changeset"],
            }

        return {
            "run1": stable(run1),
            "run1_report": report1.to_dict(),
            "run2": stable(run2),
            "run2_report": report2.to_dict(),
            "final_style": (fixture.repo / "style.txt").read_text(encoding="utf-8"),
            "clock_reads": list(fixture.clock_reads),
            "paths_under_temp": (
                fixture.repo.is_relative_to(fixture.root)
                and fixture.run1.root.is_relative_to(fixture.root)
                and fixture.run2.root.is_relative_to(fixture.root)
            ),
            "fixture_has_qb_dir": (fixture.root / ".qb").exists(),
        }

    @unittest.skipIf(subprocess.run(["git", "--version"], capture_output=True).returncode != 0, "git unavailable")
    def test_accrual_fixture_is_deterministic_and_host_state_independent(self) -> None:
        live_qb = Path.cwd() / ".qb"
        live_qb_mtime = live_qb.stat().st_mtime_ns if live_qb.exists() else None
        first = self._two_run_accrual_outcome()
        second = self._two_run_accrual_outcome()

        self.assertEqual(first, second)
        # Two 1-item run_autofix calls; run_session reads the clock 3x each (meter
        # init, ceiling check, finale telemetry build) -> 6 deterministic reads.
        self.assertEqual(first["clock_reads"],
                         [100.0, 100.25, 100.5, 100.75, 101.0, 101.25])
        self.assertTrue(first["paths_under_temp"])
        self.assertFalse(first["fixture_has_qb_dir"])
        after_live_qb_mtime = live_qb.stat().st_mtime_ns if live_qb.exists() else None
        self.assertEqual(live_qb_mtime, after_live_qb_mtime)
        self.assertIn("proxy", ACCRUAL_FIXTURE_ISOLATION_CHECKLIST["proxy-caveat"])
        self.assertIn("successive operator runs", ACCRUAL_FIXTURE_ISOLATION_CHECKLIST["proxy-caveat"])


if __name__ == "__main__":
    unittest.main()
