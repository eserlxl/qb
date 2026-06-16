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

    def _telemetry(self, kept, reverted):
        return self.t.build_telemetry(run_id="r", autonomy_level="A2", findings=[],
                                      evidence=[{"outcome": "kept", "after_exit": 0}] * kept
                                               + [{"outcome": "reverted", "after_exit": 1}] * reverted)

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

    def test_gates_fail_closed_on_malformed_telemetry(self) -> None:
        # Corrupt or hand-edited telemetry must deny (A1 max), never crash or pass open.
        for bad in ({"quality": None}, {"quality": "nope"},
                    {"quality": {"precision_estimate": "high"}},
                    {"quality": {"precision_estimate": True}},
                    {}, "not-a-dict"):
            self.assertFalse(self.rg.precision_gate(bad)[0], bad)
            self.assertFalse(self.rg.fix_safety_gate(bad)[0], bad)
            self.assertEqual(self.rg.permitted_autonomy(bad), "A1", bad)

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
            good_telemetry = self._telemetry(9, 1)

            results, _report = budget.run_session(policy, repo, items, telemetry=good_telemetry)
            self.assertEqual(results[0]["earned_ceiling"], "A2")
            self.assertEqual(results[0]["level"], "A2")
            self.assertEqual(results[0]["promoted"], ["style.txt"])
            self.assertEqual((repo / "style.txt").read_text(encoding="utf-8"), "clean\n")

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


if __name__ == "__main__":
    unittest.main()
