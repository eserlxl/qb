"""Phase 3.6 -- whole-run rollback drills over real corpus repos.

Phase 3's key acceptance signal is that rollback drills pass on real repos. After
an A2 promotion campaign, an A3 changeset campaign, or a mid-campaign kill/budget
stop, ``rollback_run`` followed by ``baseline_clean`` returns the target to its
byte-clean pre-run state at the captured HEAD. The reversal ref lives under the
dedicated ``refs/qb-baseline/`` namespace and is released afterward, touching no
user branch. Trusted/neutralized corpus only.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests import qb_corpus
from tests.qb_monorepo import REPO_ROOT, SHARED_DIR


def _load_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _driver():
    return _load_path("qb_live_validate_rb", REPO_ROOT / "scripts" / "live_validate.py")


def _release():
    return _load_path("qb_release_gate_rb", SHARED_DIR / "scripts" / "release_gate.py")


def _git(repo: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def _ref_exists(repo: Path, ref: str) -> bool:
    return _git(repo, "show-ref", "--verify", "--quiet", ref).returncode == 0


def _branches(repo: Path) -> str:
    return _git(repo, "branch", "--list").stdout


@unittest.skipIf(subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
                 "git unavailable")
class RollbackRealReposTests(unittest.TestCase):
    def _eligible(self, lv, repo, base):
        a1 = lv.run_campaign(repo, "A1", base / "a1" / repo.name / "QB-Audit")
        return lv._store.load_prior_telemetry(a1.output_dir)

    def _items(self, lv, n, prefix):
        items = []
        for i in range(n):
            name = f"{prefix}{i}.txt"
            plan = lv.make_plan(["make", "test"], finding_id=f"QBF-rb{i:09d}", evidence=f"{name}:1")
            items.append((plan, (lambda nm: (lambda iso: iso.write_file(nm, "clean\n")))(name)))
        return items

    def test_rollback_after_a2_promotion_campaign(self) -> None:
        lv, rg = _driver(), _release()
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            for repo in qb_corpus.build_corpus(base / "corpus"):
                prior = self._eligible(lv, repo, base)
                handle = rg.capture_baseline(repo.path, "rb-a2")
                a2 = lv.run_campaign(repo, "A2", base / "a2" / repo.name / "QB-Audit",
                                     prior_telemetry=prior)
                self.assertIn("fix_target.txt", a2.promoted())  # something really was promoted
                rg.rollback_run(repo.path, handle)
                self.assertTrue(rg.baseline_clean(repo.path, handle))
                rg.release_baseline(repo.path, handle)

    def test_rollback_after_a3_changeset_campaign(self) -> None:
        lv, rg = _driver(), _release()
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            for repo in qb_corpus.build_corpus(base / "corpus"):
                prior = self._eligible(lv, repo, base)
                handle = rg.capture_baseline(repo.path, "rb-a3")
                a3 = lv.run_campaign(repo, "A3", base / "a3" / repo.name / "QB-Audit",
                                     prior_telemetry=prior, enable_a3=True)
                self.assertTrue(a3.changesets())  # a changeset was assembled (no commit)
                rg.rollback_run(repo.path, handle)
                self.assertTrue(rg.baseline_clean(repo.path, handle))
                rg.release_baseline(repo.path, handle)

    def test_rollback_after_budget_stop(self) -> None:
        lv, rg = _driver(), _release()
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            for repo in qb_corpus.build_corpus(base / "corpus"):
                prior = self._eligible(lv, repo, base)
                handle = rg.capture_baseline(repo.path, "rb-stop")
                policy = lv._policy.parse_policy({
                    "autonomy_level": "A2", "auto_fixable_categories": ["quality"],
                    "default_min_confidence": "medium", "write_allowlist": ["*.txt"],
                    "budgets": {"max_fixes": 1},
                })
                _, report = lv._budget.run_session(policy, repo.path, self._items(lv, 3, "rs"),
                                                   telemetry=prior, run_id="rb-stop")
                self.assertEqual(report.trigger, "max_fixes")  # a partial, mid-campaign stop
                rg.rollback_run(repo.path, handle)
                self.assertTrue(rg.baseline_clean(repo.path, handle))
                rg.release_baseline(repo.path, handle)

    def test_reversal_ref_is_namespaced_and_released(self) -> None:
        rg = _release()
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            for repo in qb_corpus.build_corpus(base / "corpus"):
                branches_before = _branches(repo.path)
                handle = rg.capture_baseline(repo.path, "rb-ref")
                ref = f"{rg.REVERSAL_REF_PREFIX}rb-ref"
                self.assertTrue(ref.startswith("refs/qb-baseline/"))
                self.assertTrue(_ref_exists(repo.path, ref))     # created under the namespace
                rg.release_baseline(repo.path, handle)
                self.assertFalse(_ref_exists(repo.path, ref))    # released afterward
                self.assertEqual(_branches(repo.path), branches_before)  # no user branch touched


if __name__ == "__main__":
    unittest.main()
