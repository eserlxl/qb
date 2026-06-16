"""Phase 7.4 -- production gate, self-audit dogfood, kill-switch drill (finale).

Pins: the composite production gate (passes only when every conjunct holds;
fail-closed; A3 never default); the accepted-findings register; the QB-audits-QB
dogfood (a real headless self-audit completes and does NOT mutate the QB working
tree at A0); and a kill-switch drill that halts recoverably with a consistent tree.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import REPO_ROOT, SHARED_DIR

PG_PATH = SHARED_DIR / "scripts/production_gate.py"
HEADLESS_PATH = SHARED_DIR / "scripts/qb_headless.py"
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


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


class ProductionGateTests(unittest.TestCase):
    def setUp(self) -> None:
        if not PG_PATH.exists():
            self.skipTest("production_gate missing")
        self.pg = _load("qb_production_gate_under_test", PG_PATH)

    def _all_true(self):
        return dict(telemetry_emitted=True, rollback_drill_passed=True, least_privilege_ok=True,
                    supply_chain_ok=True, killswitch_proven=True, self_audit_clean=True)

    def test_gate_passes_when_all_conjuncts_hold(self) -> None:
        result = self.pg.production_gate(**self._all_true())
        self.assertTrue(result["passed"])
        self.assertEqual(result["failures"], [])
        self.assertFalse(result["a3_enabled_by_default"])  # A3 never default

    def test_gate_fails_closed_on_any_missing_conjunct(self) -> None:
        for check in self.pg.PRODUCTION_GATE_CHECKS:
            args = self._all_true()
            args[check] = False
            result = self.pg.production_gate(**args)
            self.assertFalse(result["passed"], f"gate should fail when {check} is false")
            self.assertIn(check, result["failures"])

    def test_self_audit_clean_with_accepted_register(self) -> None:
        findings = [{"id": "QBF-1"}, {"id": "QBF-2"}]
        self.assertFalse(self.pg.self_audit_clean(findings))
        self.assertTrue(self.pg.self_audit_clean(findings, accepted_ids=["QBF-1", "QBF-2"]))
        self.assertEqual([f["id"] for f in self.pg.unaccepted_findings(findings, ["QBF-1"])], ["QBF-2"])


@unittest.skipIf(subprocess.run(["git", "--version"], capture_output=True).returncode != 0, "git unavailable")
class SelfAuditDogfoodTests(unittest.TestCase):
    def setUp(self) -> None:
        if not HEADLESS_PATH.exists():
            self.skipTest("qb_headless missing")
        self.hl = _load("qb_headless_under_test", HEADLESS_PATH)

    def test_qb_audits_qb_without_mutating_the_working_tree(self) -> None:
        # The ultimate dogfood: QB headlessly audits the QB repo at A0 (report-only).
        before = _git(REPO_ROOT, "status", "--porcelain").stdout
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "QB-Audit"
            code = self.hl.run_headless(REPO_ROOT, output_dir=out)
            self.assertIn(code, (self.hl.EXIT_CLEAN, self.hl.EXIT_FINDINGS))
            self.assertTrue((out / "report.json").is_file())
        after = _git(REPO_ROOT, "status", "--porcelain").stdout
        self.assertEqual(before, after, "A0 self-audit must not mutate the QB working tree")


@unittest.skipIf(subprocess.run(["git", "--version"], capture_output=True).returncode != 0, "git unavailable")
class KillSwitchDrillTests(unittest.TestCase):
    def setUp(self) -> None:
        for p in (BUDGET_PATH, POLICY_PATH, FIXER_PATH):
            if not p.exists():
                self.skipTest("budget/policy/fixer missing")
        self.budget = _load("qb_budget_under_test", BUDGET_PATH)
        self.policy = _load("qb_policy_under_test", POLICY_PATH)
        self.fixer = _load("qb_fixer_under_test", FIXER_PATH)

    def _fixture(self, repo: Path):
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        _git(repo, "config", "user.email", "t@e.com")
        _git(repo, "config", "user.name", "t")
        _git(repo, "config", "commit.gpgsign", "false")
        (repo / "style.txt").write_text("messy\n", encoding="utf-8")
        (repo / "tests").mkdir()
        (repo / "tests" / "t.py").write_text(
            "import pathlib,unittest\nclass T(unittest.TestCase):\n"
            "    def test(self): self.assertEqual(pathlib.Path('style.txt').read_text().strip(),'clean')\n",
            encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "init")

    def test_killswitch_halts_recoverably(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            self._fixture(repo)
            policy = self.policy.parse_policy({
                "autonomy_level": "A2", "auto_fixable_categories": ["quality"],
                "default_min_confidence": "medium", "write_allowlist": ["*.txt"]})
            finding = self.fixer.Finding(
                id=self.fixer.compute_finding_id("quality", "style.txt:1", "lint"),
                category="quality", severity="P3", confidence="medium",
                evidence="style.txt:1", rationale="x", suggested_fix="y", fix_strategy="propose")
            items = [(self.fixer.plan_fix(finding, repo),
                      (lambda iso: iso.write_file("style.txt", "clean\n")))]
            ks = self.budget.KillSwitch()
            ks.trigger()  # emergency stop before any fix unit
            results, report = self.budget.run_session(policy, repo, items, killswitch=ks)
            self.assertEqual(report.trigger, "kill")
            self.assertEqual(report.exit_code, self.budget.KILL_STOP_EXIT)
            self.assertEqual(results, [])
            # tree consistent: nothing half-applied
            self.assertEqual((repo / "style.txt").read_text(), "messy\n")
            self.assertEqual(_git(repo, "status", "--porcelain").stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
