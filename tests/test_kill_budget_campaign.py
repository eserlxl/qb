"""Phase 3.5 -- kill-switch and budget-ceiling campaigns over the corpus.

An operator can stop an autonomous multi-finding campaign safely at any moment: a
kill halts at the next safe checkpoint (exit 3, no bisected fix); each of the five
budget ceilings halts exactly at its boundary (exit 2) while a clean finish
completes (exit 0); StopReport trigger/exit_code match the halt cause; and after
every stop the working tree holds no partially-applied fix.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests import qb_corpus
from tests.qb_monorepo import REPO_ROOT


def _load_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _driver():
    return _load_path("qb_live_validate_budget", REPO_ROOT / "scripts" / "live_validate.py")


def _git_porcelain(repo: Path) -> str:
    return subprocess.run(["git", "-C", str(repo), "status", "--porcelain"],
                          capture_output=True, text=True).stdout.strip()


def _policy(lv, level, budgets):
    return lv._policy.parse_policy({
        "autonomy_level": level,
        "auto_fixable_categories": ["quality"],
        "default_min_confidence": "medium",
        "write_allowlist": ["*.txt"],
        "budgets": budgets,
    })


def _green_items(lv, n, prefix="bf"):
    items = []
    for i in range(n):
        name = f"{prefix}{i}.txt"
        plan = lv.make_plan(["make", "test"], finding_id=f"QBF-budget{i:07d}", evidence=f"{name}:1")
        items.append((plan, (lambda nm: (lambda iso: iso.write_file(nm, "clean\n")))(name)))
    return items


@unittest.skipIf(subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
                 "git unavailable")
class KillBudgetCampaignTests(unittest.TestCase):
    def _repo(self, lv, base):
        return qb_corpus.build_corpus(base / "corpus")[0]

    def test_kill_switch_halts_mid_campaign(self) -> None:
        lv = _driver()
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            repo = self._repo(lv, base)
            ks = lv._budget.KillSwitch()
            ks.trigger()  # signalled before the first fix unit
            results, report = lv._budget.run_session(
                _policy(lv, "A1", {"max_fixes": 10}), repo.path, _green_items(lv, 5), killswitch=ks)
            self.assertEqual(report.trigger, "kill")
            self.assertEqual(report.exit_code, lv._budget.KILL_STOP_EXIT)
            self.assertEqual(results, [])               # halted before any unit -> none bisected
            self.assertEqual(_git_porcelain(repo.path), "")  # target tree untouched

    def test_five_ceilings_halt_at_boundary(self) -> None:
        lv = _driver()
        B = lv._budget
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            repo = self._repo(lv, base)
            _, r = B.run_session(_policy(lv, "A1", {"max_fixes": 1}), repo.path, _green_items(lv, 5))
            self.assertEqual((r.trigger, r.exit_code), ("max_fixes", B.BUDGET_STOP_EXIT))
            _, r = B.run_session(_policy(lv, "A1", {"max_iterations": 2, "max_fixes": 99}),
                                 repo.path, _green_items(lv, 5))
            self.assertEqual((r.trigger, r.exit_code), ("max_iterations", B.BUDGET_STOP_EXIT))
            _, r = B.run_session(_policy(lv, "A1", {"max_findings": 2, "max_iterations": 99, "max_fixes": 99}),
                                 repo.path, _green_items(lv, 5))
            self.assertEqual((r.trigger, r.exit_code), ("max_findings", B.BUDGET_STOP_EXIT))
            _, r = B.run_session(_policy(lv, "A1", {"max_wall_seconds": 0}), repo.path, _green_items(lv, 3))
            self.assertEqual((r.trigger, r.exit_code), ("max_wall_time", B.BUDGET_STOP_EXIT))
            # run_session does not accrue tokens, so the token ceiling is proven on the meter.
            meter = B.BudgetMeter(B.Budget(max_tokens=100))
            meter.add_tokens(100)
            self.assertEqual(meter.ceiling_reached(), "max_tokens")
            # A run that consumes all items finishes cleanly.
            _, r = B.run_session(_policy(lv, "A1", {"max_fixes": 10, "max_iterations": 10}),
                                 repo.path, _green_items(lv, 2))
            self.assertEqual((r.trigger, r.exit_code), ("completed", B.CLEAN_EXIT))

    def test_stop_report_and_exit_code_match_halt_cause(self) -> None:
        lv = _driver()
        B = lv._budget
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            repo = self._repo(lv, base)
            # completed -> 0
            _, completed = B.run_session(_policy(lv, "A1", {"max_fixes": 9}), repo.path, _green_items(lv, 2))
            self.assertEqual(completed.to_dict()["exit_code"], 0)
            self.assertEqual(completed.to_dict()["trigger"], "completed")
            # budget ceiling -> 2
            _, budget = B.run_session(_policy(lv, "A1", {"max_fixes": 1}), repo.path, _green_items(lv, 3))
            self.assertEqual(budget.to_dict()["exit_code"], 2)
            # kill -> 3
            ks = B.KillSwitch(); ks.trigger()
            _, killed = B.run_session(_policy(lv, "A1", {"max_fixes": 9}), repo.path,
                                      _green_items(lv, 3), killswitch=ks)
            self.assertEqual((killed.to_dict()["trigger"], killed.to_dict()["exit_code"]), ("kill", 3))

    def test_post_stop_tree_has_no_partial_fix(self) -> None:
        lv = _driver()
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            repo = self._repo(lv, base)
            a1 = lv.run_campaign(repo, "A1", base / "a1" / ".qb/audit")
            prior = lv._store.load_prior_telemetry(a1.output_dir)
            results, report = lv._budget.run_session(
                _policy(lv, "A2", {"max_fixes": 2}), repo.path, _green_items(lv, 5, prefix="pf"),
                telemetry=prior, run_id="pf")
            self.assertEqual(report.trigger, "max_fixes")
            promoted_on_disk = sorted(p.name for p in repo.path.glob("pf*.txt"))
            # fixes_applied correlates with whole promoted files on disk (no partials).
            self.assertEqual(len(promoted_on_disk), report.fixes_applied)
            for name in promoted_on_disk:
                self.assertEqual((repo.path / name).read_text(encoding="utf-8"), "clean\n")


if __name__ == "__main__":
    unittest.main()
