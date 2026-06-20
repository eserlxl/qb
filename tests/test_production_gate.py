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
            # Operation never implies delivery: A3 stays opt-in on a FAILING gate
            # too (complements the passing-gate assertion above).
            self.assertFalse(result["a3_enabled_by_default"],
                             f"A3 must never be default, even when {check} fails")

    def test_self_audit_clean_with_accepted_register(self) -> None:
        findings = [{"id": "QBF-1"}, {"id": "QBF-2"}]
        self.assertFalse(self.pg.self_audit_clean(findings))
        self.assertTrue(self.pg.self_audit_clean(findings, accepted_ids=["QBF-1", "QBF-2"]))
        self.assertEqual([f["id"] for f in self.pg.unaccepted_findings(findings, ["QBF-1"])], ["QBF-2"])

    def test_accepted_findings_register_loader(self) -> None:
        # Phase 7.3: the committed register parses into the accepted_ids set that
        # self_audit_clean consumes. Only backtick-wrapped ids of list items under
        # the "## Accepted" heading are read; prose, indented examples, and other
        # sections are ignored.
        af = _load("qb_accepted_findings_under_test", SHARED_DIR / "scripts/accepted_findings.py")
        sample = (
            "# Accepted findings register\n\n"
            "## Format\n"
            "    - `QBF-NOT-PARSED` -- indented example outside the section\n\n"
            "## Accepted\n"
            "- `QBF-1` -- known false positive (reviewer: maintainer)\n"
            "- `QBF-2` -- vendored fixture (reviewer: maintainer)\n"
            "Some prose mentioning `QBF-PROSE` should be ignored.\n\n"
            "## Other\n"
            "- `QBF-OTHER` -- different section\n"
        )
        ids = af.parse_accepted_ids(sample)
        self.assertEqual(ids, {"QBF-1", "QBF-2"})
        # The loader yields a set against the real repo register (currently empty).
        real = af.load_accepted_ids(REPO_ROOT)
        self.assertIsInstance(real, set)
        # An absent register accepts nothing (fail-closed).
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(af.load_accepted_ids(d), set())
        # The parsed set composes with self_audit_clean.
        self.assertTrue(self.pg.self_audit_clean([{"id": "QBF-1"}], accepted_ids=ids))
        self.assertFalse(self.pg.self_audit_clean([{"id": "QBF-X"}], accepted_ids=ids))

    def test_self_audit_reconcile_feeds_conjunct(self) -> None:
        # Phase 7.3: reconciliation loads findings.jsonl + the accepted register and
        # emits the self_audit_clean conjunct boolean plus the unaccepted-id list.
        recon = _load("qb_self_audit_reconcile_under_test",
                      SHARED_DIR / "scripts/self_audit_reconcile.py")
        with tempfile.TemporaryDirectory() as d:
            audit = Path(d) / ".qb/audit"
            audit.mkdir(parents=True)
            (audit / "findings.jsonl").write_text(
                '{"id": "QBF-A", "severity": "P3"}\n'
                '{"id": "QBF-B", "severity": "P2"}\n', encoding="utf-8")
            repo = Path(d) / "repo"
            (repo / "docs").mkdir(parents=True)

            # No register -> nothing accepted -> conjunct False, both ids unaccepted.
            result = recon.reconcile(audit, repo)
            self.assertFalse(result["self_audit_clean"])
            self.assertEqual(result["unaccepted_ids"], ["QBF-A", "QBF-B"])
            self.assertEqual(result["findings_total"], 2)

            # Accept one -> still False, only the other id remains unaccepted.
            (repo / "docs" / "accepted-findings.md").write_text(
                "## Accepted\n- `QBF-A` -- reviewed false positive (reviewer: maintainer)\n",
                encoding="utf-8")
            result = recon.reconcile(audit, repo)
            self.assertFalse(result["self_audit_clean"])
            self.assertEqual(result["unaccepted_ids"], ["QBF-B"])
            self.assertEqual(result["accepted_total"], 1)

            # Accept both -> conjunct True, no unaccepted ids.
            (repo / "docs" / "accepted-findings.md").write_text(
                "## Accepted\n"
                "- `QBF-A` -- reviewed (reviewer: maintainer)\n"
                "- `QBF-B` -- reviewed (reviewer: maintainer)\n", encoding="utf-8")
            result = recon.reconcile(audit, repo)
            self.assertTrue(result["self_audit_clean"])
            self.assertEqual(result["unaccepted_ids"], [])

        # An empty inventory (no findings.jsonl) reconciles clean (nothing to accept).
        with tempfile.TemporaryDirectory() as d:
            result = recon.reconcile(Path(d) / ".qb/audit", Path(d))
            self.assertTrue(result["self_audit_clean"])
            self.assertEqual(result["unaccepted_ids"], [])

    def test_unaccepted_finding_keeps_gate_closed(self) -> None:
        # Phase 7.3 fail-closed: a finding that is neither fixed nor in the accepted
        # register keeps self_audit_clean False and is named EXACTLY in
        # unaccepted_findings -- and that False denies the composite production gate.
        findings = [{"id": "QBF-ACCEPTED-1"}, {"id": "QBF-UNREVIEWED"}, {"id": "QBF-ACCEPTED-2"}]
        accepted = ["QBF-ACCEPTED-1", "QBF-ACCEPTED-2"]
        self.assertFalse(self.pg.self_audit_clean(findings, accepted_ids=accepted))
        self.assertEqual(
            [f["id"] for f in self.pg.unaccepted_findings(findings, accepted_ids=accepted)],
            ["QBF-UNREVIEWED"])
        # The unclean self-audit denies the composite gate, naming the conjunct.
        args = self._all_true()
        args["self_audit_clean"] = self.pg.self_audit_clean(findings, accepted_ids=accepted)
        result = self.pg.production_gate(**args)
        self.assertFalse(result["passed"])
        self.assertIn("self_audit_clean", result["failures"])


class ProductionGateSignalsTests(unittest.TestCase):
    def setUp(self) -> None:
        signals_path = SHARED_DIR / "scripts/production_gate_signals.py"
        if not signals_path.exists():
            self.skipTest("production_gate_signals missing")
        self.sig = _load("qb_production_gate_signals_under_test", signals_path)
        self.store = _load("qb_run_store_for_signals", SHARED_DIR / "scripts/run_store.py")
        self.recov = _load("qb_recoverability_for_signals", SHARED_DIR / "scripts/recoverability_drill.py")

    def _all_real_signals(self, d):
        audit = Path(d) / ".qb/audit"
        store = self.store.RunStore(audit).open()
        store.write_telemetry({"schema_version": 1,
                               "quality": {"precision_estimate": 0.95, "fix_safety_ok": True}})
        store.write_findings([])  # clean self-audit inventory (every finding fixed)
        self.recov.persist_evidence(
            {"schema_version": 1, "run_id": "r", "baseline_ref": "refs/qb-baseline/r",
             "baseline_sha_len": 40, "baseline_clean": True, "passed": True}, audit)
        repo = Path(d) / "repo"
        repo.mkdir()
        return audit, repo

    def test_assemble_six_signals_from_real_sources(self) -> None:
        # Phase 7.4: with all six conjuncts derived True from real sources, the
        # composite gate passes, names no failures, and never enables A3 by default.
        with tempfile.TemporaryDirectory() as d:
            audit, repo = self._all_real_signals(d)
            decision = self.sig.gate_decision(audit, repo, scripts_dir=SHARED_DIR / "scripts")
            self.assertTrue(decision["passed"], decision["failures"])
            self.assertEqual(decision["failures"], [])
            self.assertFalse(decision["a3_enabled_by_default"])
            for name, value in decision["signals"].items():
                self.assertTrue(value, f"signal {name} should be true from real sources")
            # the six derived conjuncts exactly match the engine's check set
            self.assertEqual(set(decision["signals"]), set(self.sig._pg.PRODUCTION_GATE_CHECKS))
            self.assertEqual(decision["permitted_autonomy"], "A2")  # earned ceiling surfaced

    def test_supply_chain_signal_is_real_not_placeholder(self) -> None:
        # The interim supply_chain_ok is derived from the dependency-free core, not a
        # hardcoded True: a directory with a non-stdlib import fails it.
        self.assertTrue(self.sig.supply_chain_ok(SHARED_DIR / "scripts"))
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "tainted.py").write_text("import requests\n", encoding="utf-8")
            self.assertFalse(self.sig.supply_chain_ok(d))

    def test_supply_chain_fails_closed_on_unparseable_module(self) -> None:
        # Fail-closed: a module that cannot be read/parsed cannot be proven
        # dependency-free, so it must DENY the supply-chain conjunct rather than
        # be silently skipped (which would let a corrupt engine file pass clean).
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "broken.py").write_text("def f(:\n", encoding="utf-8")
            self.assertFalse(
                self.sig.supply_chain_ok(d),
                "an unparseable engine module must fail the supply-chain check closed",
            )

    def test_each_missing_signal_fails_the_gate(self) -> None:
        # Fail-closed: an absent telemetry record / recoverability record / findings
        # inventory each deny their conjunct (so the composite gate cannot pass).
        with tempfile.TemporaryDirectory() as d:
            empty_audit = Path(d) / ".qb/audit"
            empty_audit.mkdir(parents=True)
            repo = Path(d) / "repo"
            repo.mkdir()
            self.assertFalse(self.sig.telemetry_emitted(empty_audit))
            self.assertFalse(self.sig.rollback_drill_passed(empty_audit))
            decision = self.sig.gate_decision(
                empty_audit, repo, scripts_dir=SHARED_DIR / "scripts")
            self.assertFalse(decision["passed"])
            self.assertFalse(decision["signals"]["telemetry_emitted"])
            self.assertFalse(decision["signals"]["rollback_drill_passed"])
            self.assertIn("telemetry_emitted", decision["failures"])
            self.assertIn("rollback_drill_passed", decision["failures"])
            self.assertEqual(decision["permitted_autonomy"], "A1")

    def test_single_broken_real_signal_denies_gate_with_named_failure(self) -> None:
        # Phase 7.4: at the ASSEMBLY level, breaking ONE real signal source (the
        # others left real-True) denies the gate with EXACTLY that conjunct named in
        # failures -- the per-signal routing the literal-boolean gate test cannot see.
        # (least_privilege_ok / killswitch_proven are proven-positive above and have no
        # fixture-breakable source, so the four source-breakable conjuncts are covered.)
        scripts = SHARED_DIR / "scripts"

        with tempfile.TemporaryDirectory() as d:  # telemetry_emitted
            audit, repo = self._all_real_signals(d)
            (audit / "telemetry.json").unlink()
            decision = self.sig.gate_decision(audit, repo, scripts_dir=scripts)
            self.assertFalse(decision["passed"])
            self.assertEqual(decision["failures"], ["telemetry_emitted"])

        with tempfile.TemporaryDirectory() as d:  # rollback_drill_passed
            audit, repo = self._all_real_signals(d)
            (audit / "recoverability.json").unlink()
            decision = self.sig.gate_decision(audit, repo, scripts_dir=scripts)
            self.assertFalse(decision["passed"])
            self.assertEqual(decision["failures"], ["rollback_drill_passed"])

        with tempfile.TemporaryDirectory() as d:  # self_audit_clean
            audit, repo = self._all_real_signals(d)
            (audit / "findings.jsonl").write_text('{"id": "QBF-UNREVIEWED"}\n', encoding="utf-8")
            decision = self.sig.gate_decision(audit, repo, scripts_dir=scripts)
            self.assertFalse(decision["passed"])
            self.assertEqual(decision["failures"], ["self_audit_clean"])

        with tempfile.TemporaryDirectory() as d:  # supply_chain_ok
            audit, repo = self._all_real_signals(d)
            tainted = Path(d) / "tainted-scripts"
            tainted.mkdir()
            (tainted / "x.py").write_text("import requests\n", encoding="utf-8")
            decision = self.sig.gate_decision(audit, repo, scripts_dir=tainted)
            self.assertFalse(decision["passed"])
            self.assertEqual(decision["failures"], ["supply_chain_ok"])

        with tempfile.TemporaryDirectory() as d:  # killswitch_proven
            audit, repo = self._all_real_signals(d)
            original = self.sig.prove_killswitch
            try:
                self.sig.prove_killswitch = lambda: False
                decision = self.sig.gate_decision(audit, repo, scripts_dir=scripts)
            finally:
                self.sig.prove_killswitch = original
            self.assertFalse(decision["passed"])
            self.assertEqual(decision["failures"], ["killswitch_proven"])

    def test_gate_re_evaluates_on_signal_regression(self) -> None:
        # Phase 7.4: the gate re-evaluates CURRENT signals; it is not a one-time
        # checkbox. The same context that passes once must fail again when a current
        # signal regresses between evaluations.
        scripts = SHARED_DIR / "scripts"
        with tempfile.TemporaryDirectory() as d:
            audit, repo = self._all_real_signals(d)
            first = self.sig.gate_decision(audit, repo, scripts_dir=scripts)
            self.assertTrue(first["passed"], first["failures"])

            # Regress a current signal: the rollback drill record now records a failure.
            (audit / "recoverability.json").write_text(
                '{"schema_version": 1, "run_id": "r", "passed": false}\n', encoding="utf-8")
            second = self.sig.gate_decision(audit, repo, scripts_dir=scripts)
            self.assertFalse(second["passed"])
            self.assertIn("rollback_drill_passed", second["failures"])

            # And it recovers on re-evaluation once the signal is healthy again.
            (audit / "recoverability.json").write_text(
                '{"schema_version": 1, "run_id": "r", "passed": true}\n', encoding="utf-8")
            third = self.sig.gate_decision(audit, repo, scripts_dir=scripts)
            self.assertTrue(third["passed"], third["failures"])


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
            out = Path(d) / ".qb/audit"
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
