"""Phase 7.2 -- rollback drill + release gates.

Pins: whole-run capture/undo on a real temp git repo (clean tree at baseline,
namespaced reversal ref that does not collide with user branches); and the
fail-closed precision + fix-safety release gates and their gate-to-autonomy map.
"""

from __future__ import annotations

import ast
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

GATE_PATH = SHARED_DIR / "scripts/release_gate.py"
TELEMETRY_PATH = SHARED_DIR / "scripts/telemetry.py"
BUDGET_PATH = SHARED_DIR / "scripts/budget.py"
POLICY_PATH = SHARED_DIR / "scripts/policy.py"
FIXER_PATH = SHARED_DIR / "scripts/fixer.py"
ORCH_PATH = SHARED_DIR / "scripts/orchestrator.py"


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


def _init_repo(d: Path) -> None:
    subprocess.run(["git", "init", "-q", str(d)], check=True)
    _git(d, "config", "user.email", "t@example.com")
    _git(d, "config", "user.name", "QB Test")
    _git(d, "config", "commit.gpgsign", "false")
    (d / "a.txt").write_text("original\n", encoding="utf-8")
    _git(d, "add", "-A")
    _git(d, "commit", "-q", "-m", "init")


def _init_autofix_repo(d: Path) -> None:
    _init_repo(d)
    (d / "style.txt").write_text("messy\n", encoding="utf-8")
    tests_dir = d / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_style.py").write_text(
        "import pathlib, unittest\n"
        "class T(unittest.TestCase):\n"
        "    def test_clean(self):\n"
        "        self.assertEqual(pathlib.Path('style.txt').read_text().strip(), 'clean')\n",
        encoding="utf-8",
    )
    _git(d, "add", "-A")
    _git(d, "commit", "-q", "-m", "autofix fixture")


@unittest.skipIf(subprocess.run(["git", "--version"], capture_output=True).returncode != 0, "git unavailable")
class RollbackDrillTests(unittest.TestCase):
    def setUp(self) -> None:
        if not GATE_PATH.exists():
            self.skipTest("release_gate missing")
        self.rg = _load("qb_release_gate_under_test", GATE_PATH)
        self.t = _load("qb_telemetry_under_test", TELEMETRY_PATH)

    def test_full_run_rollback_drill_passes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _init_repo(repo)

            def mutate(r):
                (r / "a.txt").write_text("CHANGED\n", encoding="utf-8")   # modify tracked
                (r / "b.txt").write_text("new file\n", encoding="utf-8")  # add untracked

            self.assertTrue(self.rg.run_rollback_drill(repo, "drill", mutate))
            # tree restored exactly
            self.assertEqual((repo / "a.txt").read_text(), "original\n")
            self.assertFalse((repo / "b.txt").exists())
            self.assertEqual(_git(repo, "status", "--porcelain").stdout.strip(), "")

    def test_reversal_ref_is_namespaced_and_cleaned_up(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _init_repo(repo)
            handle = self.rg.capture_baseline(repo, "ns")
            self.assertTrue(handle["ref"].startswith("refs/qb-baseline/"))
            # not a normal branch -> never collides with user branches
            self.assertEqual(_git(repo, "branch", "--list").stdout.strip(), "* " + _git(repo, "branch", "--show-current").stdout.strip())
            self.rg.release_baseline(repo, handle)
            self.assertNotEqual(_git(repo, "show-ref", handle["ref"]).returncode, 0)

    def test_partial_rollback_fails_closed(self) -> None:
        # Phase 7.1 negative path: a partial/corrupt rollback must report FAILURE,
        # never a silent pass. Proven two ways -- residue the rollback cannot remove,
        # and a divergent HEAD even with an otherwise-clean tree.
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _init_repo(repo)

            # (1) Residue survives rollback: a nested git repo is skipped by
            # `git clean -fd`, so the tree never returns to baseline -> drill False.
            def mutate_with_residue(r):
                (Path(r) / "a.txt").write_text("CHANGED\n", encoding="utf-8")
                nested = Path(r) / "nested"
                nested.mkdir()
                subprocess.run(["git", "init", "-q", str(nested)], check=True)
                (nested / "f.txt").write_text("residue\n", encoding="utf-8")

            self.assertFalse(self.rg.run_rollback_drill(repo, "residue", mutate_with_residue))
            # the drill did not silently pass: residue is still present after rollback
            self.assertTrue((repo / "nested").exists())
            self.assertNotEqual(_git(repo, "status", "--porcelain").stdout.strip(), "")
            # even a FAILED drill releases its reversal ref (run_rollback_drill's
            # finally): no refs/qb-baseline/* leaks after the failure.
            self.assertEqual(
                _git(repo, "for-each-ref", "refs/qb-baseline/").stdout.strip(), "",
                "a failed (residue) drill must not leak a refs/qb-baseline/* ref")

        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _init_repo(repo)
            handle = self.rg.capture_baseline(repo, "divergent")
            # (2) Divergent HEAD with a clean tree: a rollback that lands on the wrong
            # commit must still read as not-clean (HEAD != captured baseline sha).
            (repo / "a.txt").write_text("v2\n", encoding="utf-8")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "advance HEAD")
            self.assertEqual(_git(repo, "status", "--porcelain").stdout.strip(), "")  # clean tree
            self.assertNotEqual(_git(repo, "rev-parse", "HEAD").stdout.strip(), handle["sha"])
            self.assertFalse(self.rg.baseline_clean(repo, handle))  # fail-closed on HEAD drift
            self.rg.release_baseline(repo, handle)

    def test_mutation_exception_rolls_back_and_fails_drill(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _init_repo(repo)

            def mutate(r):
                (Path(r) / "a.txt").write_text("CHANGED\n", encoding="utf-8")
                (Path(r) / "b.txt").write_text("new file\n", encoding="utf-8")
                raise RuntimeError("fixture failure")

            self.assertFalse(self.rg.run_rollback_drill(repo, "raises", mutate))
            self.assertEqual((repo / "a.txt").read_text(), "original\n")
            self.assertFalse((repo / "b.txt").exists())
            self.assertEqual(_git(repo, "status", "--porcelain").stdout.strip(), "")
            # the reversal ref is released even when the drill fails on an exception
            self.assertEqual(
                _git(repo, "for-each-ref", "refs/qb-baseline/").stdout.strip(), "",
                "an exception-failed drill must not leak a refs/qb-baseline/* ref")

    def test_authorize_release_gate_on_recorded_telemetry(self) -> None:
        # Phase 7.2: authorize the earned-autonomy ceiling against a RECORDED
        # telemetry.json (persisted to the run store and read back), not just an
        # in-memory dict. A2 is granted only when precision_estimate >=
        # PRECISION_FLOOR AND fix_safety_ok; any other recorded shape caps at A1.
        store = _load("qb_run_store_for_release_gate_test", SHARED_DIR / "scripts/run_store.py")

        def _record(run_id, evidence):
            with tempfile.TemporaryDirectory() as d:
                rs = store.RunStore(Path(d) / ".qb/audit").open()
                rs.write_telemetry(self.t.build_telemetry(
                    run_id=run_id, autonomy_level="A2", findings=[], evidence=evidence))
                return rs.read_telemetry()

        # Granted: precision 0.9 >= floor, fix-safety clean -> A2.
        granted = _record("rec-a2",
                          [{"outcome": "kept", "after_exit": 0}] * 9
                          + [{"outcome": "reverted", "after_exit": 1}])
        self.assertGreaterEqual(granted["quality"]["precision_estimate"], self.rg.PRECISION_FLOOR)
        self.assertTrue(granted["quality"]["fix_safety_ok"])
        self.assertEqual(self.rg.permitted_autonomy(granted), "A2")

        # Below floor: precision 0.1 < floor -> denied (A1).
        below = _record("rec-a1",
                        [{"outcome": "kept", "after_exit": 0}]
                        + [{"outcome": "reverted", "after_exit": 1}] * 9)
        self.assertLess(below["quality"]["precision_estimate"], self.rg.PRECISION_FLOOR)
        self.assertEqual(self.rg.permitted_autonomy(below), "A1")

        # Fix-safety breach (a kept fix did not verify green) -> denied even at high precision.
        breach = _record("rec-breach",
                         [{"outcome": "kept", "after_exit": 0}] * 8
                         + [{"outcome": "kept", "after_exit": 3}])
        self.assertFalse(breach["quality"]["fix_safety_ok"])
        self.assertEqual(self.rg.permitted_autonomy(breach), "A1")

    def test_read_authorization_degrades_on_malformed_record(self) -> None:
        # A corrupt/partial release-authorization.json must read back as {} (the
        # same default as an absent file), like the hardened run_store readers --
        # never raise JSONDecodeError to the caller.
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            (out / self.rg.AUTHORIZATION_EVIDENCE_FILENAME).write_text(
                "{not valid json", encoding="utf-8")
            self.assertEqual(self.rg.read_authorization(out), {})
            # A valid record still round-trips through persist/read, schema-versioned.
            record = self.rg.authorization_record(self._telemetry(9, 1))
            self.rg.persist_authorization(record, out)
            loaded = self.rg.read_authorization(out)
            self.assertEqual(loaded["permitted_autonomy"], "A2")
            self.assertEqual(loaded["schema_version"],
                             self.rg.AUTHORIZATION_EVIDENCE_SCHEMA_VERSION)
            # persist_authorization redacts: an injected secret-shaped value is never
            # written to disk (defense in depth -- the record carries no raw values).
            secret = "ghp_" + "B" * 30
            persisted = self.rg.persist_authorization({**record, "note": secret}, out)
            raw = persisted.read_text(encoding="utf-8")
            self.assertNotIn(secret, raw)
            self.assertIn("<redacted>", raw)

    def _telemetry(self, kept, reverted):
        return self.t.build_telemetry(run_id="r", autonomy_level="A2", findings=[],
                                      evidence=[{"outcome": "kept", "after_exit": 0}] * kept
                                               + [{"outcome": "reverted", "after_exit": 1}] * reverted)

    def _budget_autofix_result(self, telemetry, *, autonomy_level="A2", enable_a3=False):
        budget = _load("qb_budget_for_release_gate_test", BUDGET_PATH)
        policy_mod = _load("qb_policy_for_release_gate_test", POLICY_PATH)
        fixer = _load("qb_fixer_for_release_gate_test", FIXER_PATH)
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _init_autofix_repo(repo)
            policy = policy_mod.parse_policy({
                "autonomy_level": autonomy_level,
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
            plan = fixer.plan_fix(finding, repo)
            items = [(plan, lambda iso: iso.write_file("style.txt", "clean\n"))]
            results, _report = budget.run_session(
                policy, repo, items, telemetry=telemetry, enable_a3=enable_a3)
            return results[0], (repo / "style.txt").read_text(encoding="utf-8")

    def test_precision_gate_fail_closed(self) -> None:
        self.assertFalse(self.rg.precision_gate(self._telemetry(0, 0))[0])      # no data
        self.assertTrue(self.rg.precision_gate(self._telemetry(9, 1))[0])       # 0.9 >= 0.8
        self.assertFalse(self.rg.precision_gate(self._telemetry(1, 9))[0])      # 0.1 < 0.8

    def test_fix_safety_gate(self) -> None:
        good = self.t.build_telemetry(run_id="r", autonomy_level="A2", findings=[],
                                      evidence=[{"outcome": "kept", "after_exit": 0}])
        bad = self.t.build_telemetry(run_id="r", autonomy_level="A2", findings=[],
                                     evidence=[{"outcome": "kept", "after_exit": 3}])
        self.assertTrue(self.rg.fix_safety_gate(good)[0])
        self.assertFalse(self.rg.fix_safety_gate(bad)[0])

    def test_permitted_autonomy_mapping(self) -> None:
        self.assertEqual(self.rg.permitted_autonomy(self._telemetry(9, 1)), "A2")
        self.assertEqual(self.rg.permitted_autonomy(self._telemetry(1, 9)), "A1")
        self.assertEqual(self.rg.permitted_autonomy(self._telemetry(0, 0)), "A1")  # fail-closed

    def test_precision_floor_boundary_is_inclusive(self) -> None:
        # Boundary: precision_gate denies on `precision < floor`, so precision
        # EXACTLY at the floor earns A2 (inclusive) while just below denies to A1 --
        # the >=-floor decision the 0.9/0.1 cases leave unpinned. The autonomy clamp
        # is most_restrictive, so a fix-safety breach at the floor still denies.
        floor = self.rg.PRECISION_FLOOR
        at_floor = {"quality": {"precision_estimate": floor, "fix_safety_ok": True}}
        below = {"quality": {"precision_estimate": floor - 0.01, "fix_safety_ok": True}}
        breach_at_floor = {"quality": {"precision_estimate": floor, "fix_safety_ok": False}}
        self.assertEqual(self.rg.permitted_autonomy(at_floor), "A2",
                         "precision exactly at the floor must earn A2 (inclusive)")
        self.assertEqual(self.rg.permitted_autonomy(below), "A1",
                         "precision just below the floor must deny A2")
        self.assertEqual(self.rg.permitted_autonomy(breach_at_floor), "A1",
                         "a fix-safety breach denies even at the precision floor")

    def test_gates_fail_closed_on_malformed_telemetry(self) -> None:
        # Corrupt or hand-edited telemetry must deny (A1 max), never crash or pass open.
        for bad in ({"quality": None}, {"quality": "nope"},
                    {"quality": {"precision_estimate": "high"}},
                    {"quality": {"precision_estimate": True}},
                    {}, "not-a-dict"):
            self.assertFalse(self.rg.precision_gate(bad)[0], bad)
            self.assertFalse(self.rg.fix_safety_gate(bad)[0], bad)
            self.assertEqual(self.rg.permitted_autonomy(bad), "A1", bad)

    def test_permitted_autonomy_fails_closed_on_malformed_telemetry(self) -> None:
        # Phase 7.2: the autonomy decision fed to the finale must always be SAFE.
        # Every malformed/partial telemetry shape must deny auto-apply (cap A1)
        # WITHOUT raising -- including a record whose precision passes but whose
        # fix_safety_ok key is missing (it must NOT silently grant A2).
        malformed = [
            {"quality": None},                                       # quality=null
            "not-a-dict",                                            # non-dict telemetry
            None,                                                    # None telemetry
            {"quality": {"precision_estimate": True,                 # boolean precision
                         "fix_safety_ok": True}},
            {"quality": {"precision_estimate": "0.95",               # non-numeric precision
                         "fix_safety_ok": True}},
            {"quality": {"precision_estimate": 0.95}},               # missing fix_safety_ok
            {"quality": {"fix_safety_ok": True}},                    # missing precision
        ]
        for bad in malformed:
            try:
                level = self.rg.permitted_autonomy(bad)
            except Exception as exc:  # the decision must fail closed, never crash
                self.fail(f"permitted_autonomy raised on {bad!r}: {exc!r}")
            self.assertEqual(level, "A1", bad)

    def test_budget_threads_loaded_telemetry_to_single_orchestrator_clamp(self) -> None:
        budget = _load("qb_budget_for_release_gate_test", BUDGET_PATH)
        policy_mod = _load("qb_policy_for_release_gate_test", POLICY_PATH)
        fixer = _load("qb_fixer_for_release_gate_test", FIXER_PATH)
        tree = ast.parse(ORCH_PATH.read_text(encoding="utf-8"))
        clamp_calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "permitted_autonomy"
        ]
        self.assertEqual(len(clamp_calls), 1)

        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _init_autofix_repo(repo)
            finding = fixer.Finding(
                id=fixer.compute_finding_id("quality", "style.txt:1", "lint"),
                category="quality", severity="P3", confidence="medium",
                evidence="style.txt:1", rationale="x", suggested_fix="y",
                fix_strategy="autofix",
            )
            plan = fixer.plan_fix(finding, repo)

            def _apply_edge_case_changes(iso):
                iso.write_file("style.txt", "clean\n")
                (Path(iso.worktree_path) / "a.txt").unlink()
                (Path(iso.worktree_path) / "binary.dat").write_bytes(b"\x00\xffqb")
                byproduct = Path(iso.worktree_path) / "__pycache__"
                byproduct.mkdir()
                (byproduct / "ignored.pyc").write_bytes(b"cache")

            policy = policy_mod.parse_policy({
                "autonomy_level": "A2",
                "auto_fixable_categories": ["quality"],
                "default_min_confidence": "medium",
                "write_allowlist": ["style.txt", "a.txt", "binary.dat"],
            })
            items = [(plan, _apply_edge_case_changes)]
            good_telemetry = self._telemetry(9, 1)

            results, _report = budget.run_session(policy, repo, items, telemetry=good_telemetry)
            self.assertEqual(results[0]["earned_ceiling"], "A2")
            self.assertEqual(results[0]["level"], "A2")
            self.assertEqual(
                set(results[0]["promoted"]),
                {"a.txt", "binary.dat", "style.txt"},
            )
            self.assertEqual((repo / "style.txt").read_text(encoding="utf-8"), "clean\n")
            self.assertFalse((repo / "a.txt").exists(), "tracked deletions must promote")
            self.assertEqual((repo / "binary.dat").read_bytes(), b"\x00\xffqb")
            self.assertFalse(
                (repo / "__pycache__").exists(),
                "incidental byproducts must not promote",
            )

        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _init_autofix_repo(repo)
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
            plan = fixer.plan_fix(finding, repo)
            items = [(plan, lambda iso: iso.write_file("style.txt", "clean\n"))]

            results, _report = budget.run_session(policy, repo, items, telemetry=None)
            self.assertEqual(results[0]["earned_ceiling"], "A1")
            self.assertEqual(results[0]["level"], "A1")
            self.assertEqual(results[0]["promoted"], [])
            self.assertEqual((repo / "style.txt").read_text(encoding="utf-8"), "messy\n")

    def test_loaded_telemetry_ceiling_controls_declared_autonomy(self) -> None:
        result, content = self._budget_autofix_result(self._telemetry(9, 1))
        self.assertEqual(result["earned_ceiling"], "A2")
        self.assertEqual(result["level"], "A2")
        self.assertEqual(result["promoted"], ["style.txt"])
        self.assertEqual(content, "clean\n")

        for bad in (self._telemetry(1, 9), {}, {"quality": None},
                    {"quality": {"precision_estimate": True, "fix_safety_ok": True}},
                    "not-a-dict"):
            result, content = self._budget_autofix_result(bad)
            self.assertEqual(result["earned_ceiling"], "A1", bad)
            self.assertEqual(result["level"], "A1", bad)
            self.assertEqual(result["promoted"], [], bad)
            self.assertEqual(content, "messy\n", bad)

        result, content = self._budget_autofix_result(self._telemetry(9, 1), autonomy_level="A0")
        self.assertEqual(result["earned_ceiling"], "A2")
        self.assertEqual(result["level"], "A0")
        self.assertEqual(result["outcome"], "report-only")
        self.assertEqual(result["promoted"], [])
        self.assertEqual(content, "messy\n")

    def test_declared_a3_over_empty_telemetry_cannot_bypass_clamp(self) -> None:
        result, content = self._budget_autofix_result({}, autonomy_level="A3", enable_a3=True)
        self.assertEqual(result["declared_level"], "A3")
        self.assertEqual(result["earned_ceiling"], "A1")
        self.assertEqual(result["level"], "A1")
        self.assertEqual(result["promoted"], [])
        self.assertIsNone(result["changeset"])
        self.assertEqual(content, "messy\n")

        policy_mod = _load("qb_policy_for_release_gate_test", POLICY_PATH)
        fixer = _load("qb_fixer_for_release_gate_test", FIXER_PATH)
        orch = _load("qb_orchestrator_for_release_gate_review_test", ORCH_PATH)
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _init_autofix_repo(repo)
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
            plan = fixer.plan_fix(finding, repo)
            result = orch.run_finding(
                policy,
                repo,
                plan,
                lambda iso: iso.write_file("style.txt", "clean\n"),
                telemetry=self._telemetry(9, 1),
                review=lambda _finding: {
                    "promote": False,
                    "reason": "review-demoted",
                },
            )
            self.assertEqual(result["outcome"], "blocked")
            self.assertEqual(result["reason"], "review-demoted")
            self.assertEqual(result["promoted"], [])
            self.assertEqual((repo / "style.txt").read_text(encoding="utf-8"), "messy\n")


if __name__ == "__main__":
    unittest.main()
