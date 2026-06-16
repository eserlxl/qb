"""Phase 4.3 -- budgets + kill-switch.

Pins: stop-at-ceiling for each budget axis (check before consuming the next unit),
the distinct headless exit codes (clean / budget-stop / kill-stop), kill-switch
honored at safe checkpoints with a consistent tree (no half-applied fix), and the
stop-report contents. Runs the full session over real temp git fixtures.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

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


def _build_fixture(repo: Path) -> None:
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "QB Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "style.txt").write_text("messy\n", encoding="utf-8")
    tdir = repo / "tests"
    tdir.mkdir()
    (tdir / "test_style.py").write_text(
        "import pathlib, unittest\n"
        "class T(unittest.TestCase):\n"
        "    def test_clean(self):\n"
        "        self.assertEqual(pathlib.Path('style.txt').read_text().strip(), 'clean')\n",
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")


@unittest.skipIf(subprocess.run(["git", "--version"], capture_output=True).returncode != 0, "git unavailable")
class BudgetTests(unittest.TestCase):
    def setUp(self) -> None:
        for path in (BUDGET_PATH, POLICY_PATH, FIXER_PATH):
            if not path.exists():
                self.skipTest(f"missing module: {path}")
        self.budget = _load("qb_budget_under_test", BUDGET_PATH)
        self.policy = _load("qb_policy_under_test", POLICY_PATH)
        self.fixer = _load("qb_fixer_under_test", FIXER_PATH)

    def _policy(self, budgets):
        return self.policy.parse_policy({
            "autonomy_level": "A2",
            "auto_fixable_categories": ["quality"],
            "default_min_confidence": "medium",
            "write_allowlist": ["*.txt"],
            "budgets": budgets,
        })

    def _items(self, repo, n):
        finding = self.fixer.Finding(
            id=self.fixer.compute_finding_id("quality", "style.txt:1", "lint"),
            category="quality", severity="P3", confidence="medium",
            evidence="style.txt:1", rationale="x", suggested_fix="y", fix_strategy="propose",
        )
        plan = self.fixer.plan_fix(finding, repo)
        return [(plan, (lambda iso: iso.write_file("style.txt", "clean\n"))) for _ in range(n)]

    def test_clean_finish_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _build_fixture(repo)
            _results, report = self.budget.run_session(
                self._policy({"max_fixes": 10, "max_iterations": 10}), repo, self._items(repo, 2))
            self.assertEqual(report.trigger, "completed")
            self.assertEqual(report.exit_code, self.budget.CLEAN_EXIT)

    def test_stops_at_max_fixes_ceiling(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _build_fixture(repo)
            results, report = self.budget.run_session(
                self._policy({"max_fixes": 1}), repo, self._items(repo, 5))
            self.assertEqual(report.trigger, "max_fixes")
            self.assertEqual(report.exit_code, self.budget.BUDGET_STOP_EXIT)
            self.assertEqual(report.fixes_applied, 1)        # stopped AT the ceiling
            self.assertEqual(len(results), 1)                # did not exceed

    def test_stops_at_max_iterations_ceiling(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _build_fixture(repo)
            results, report = self.budget.run_session(
                self._policy({"max_iterations": 2, "max_fixes": 99}), repo, self._items(repo, 5))
            self.assertEqual(report.trigger, "max_iterations")
            self.assertEqual(len(results), 2)

    def test_stops_at_max_wall_time_immediately(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _build_fixture(repo)
            results, report = self.budget.run_session(
                self._policy({"max_wall_seconds": 0}), repo, self._items(repo, 3))
            self.assertEqual(report.trigger, "max_wall_time")
            self.assertEqual(len(results), 0)                # stops before consuming any unit

    def test_kill_switch_stops_at_safe_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _build_fixture(repo)
            ks = self.budget.KillSwitch()
            ks.trigger()  # signalled before the first unit
            results, report = self.budget.run_session(
                self._policy({"max_fixes": 10}), repo, self._items(repo, 3), killswitch=ks)
            self.assertEqual(report.trigger, "kill")
            self.assertEqual(report.exit_code, self.budget.KILL_STOP_EXIT)
            self.assertEqual(len(results), 0)
            # tree consistent: nothing half-applied
            self.assertEqual((repo / "style.txt").read_text(), "messy\n")

    def test_meter_token_ceiling(self) -> None:
        budget = self.budget.Budget(max_tokens=100)
        meter = self.budget.BudgetMeter(budget)
        self.assertIsNone(meter.ceiling_reached())
        meter.add_tokens(100)
        self.assertEqual(meter.ceiling_reached(), "max_tokens")


if __name__ == "__main__":
    unittest.main()
