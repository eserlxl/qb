"""Phase 3.3 -- the A2 promotion campaign.

With loaded A2-eligible telemetry, A2 promotes a green-verified fix into the
working tree; poor or breached telemetry denies promotion (earned ceiling A1);
green fixes are kept and promoted while non-green fixes auto-revert and never
reach the tree; and measured precision matches the corpus ground truth and clears
PRECISION_FLOOR. Trusted/neutralized corpus only.
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
    return _load_path("qb_live_validate_a2", REPO_ROOT / "scripts" / "live_validate.py")


_POOR = {"quality": {"precision_estimate": 0.10, "fix_safety_ok": True}}
_BREACHED = {"quality": {"precision_estimate": 0.95, "fix_safety_ok": False}}


@unittest.skipIf(subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
                 "git unavailable")
class A2CampaignTests(unittest.TestCase):
    def _eligible_telemetry(self, lv, repo, base):
        a1 = lv.run_campaign(repo, "A1", base / "a1" / repo.name / "QB-Audit")
        return lv._store.load_prior_telemetry(a1.output_dir)

    def test_a2_promotes_with_loaded_eligible_telemetry(self) -> None:
        lv = _driver()
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            for repo in qb_corpus.build_corpus(base / "corpus"):
                prior = self._eligible_telemetry(lv, repo, base)
                self.assertEqual(lv._telemetry.max_permitted_autonomy(prior), "A2")
                a2 = lv.run_campaign(repo, "A2", base / "a2" / repo.name / "QB-Audit",
                                     prior_telemetry=prior)
                self.assertIn("kept", a2.outcomes())
                self.assertIn("fix_target.txt", a2.promoted())
                self.assertTrue((repo.path / "fix_target.txt").exists())  # promoted to the tree

    def test_poor_and_breached_telemetry_deny_promotion(self) -> None:
        lv = _driver()
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            for repo in qb_corpus.build_corpus(base / "corpus"):
                for label, prior in (("poor", _POOR), ("breached", _BREACHED)):
                    run = lv.run_campaign(repo, "A2", base / label / repo.name / "QB-Audit",
                                          prior_telemetry=prior)
                    for result in run.results:
                        self.assertEqual(result["earned_ceiling"], "A1", f"{repo.name} {label}")
                    self.assertEqual(run.promoted(), [], f"{repo.name} {label}")

    def test_green_kept_promoted_nongreen_reverted_never_promoted(self) -> None:
        lv = _driver()
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            for repo in qb_corpus.build_corpus(base / "corpus"):
                prior = self._eligible_telemetry(lv, repo, base)
                policy = lv.session_policy("A2")
                green = lv.make_plan(["make", "test"], finding_id="QBF-green0000000",
                                     evidence="fix_target.txt:1")
                bad = lv.make_plan(["python3", "-c", "import sys; sys.exit(1)"],
                                   finding_id="QBF-bad00000000", evidence="bad.txt:1")
                items = [
                    (green, lambda iso: iso.write_file("fix_target.txt", "clean\n")),
                    (bad, lambda iso: iso.write_file("bad.txt", "x\n")),
                ]
                results, _ = lv._budget.run_session(policy, repo.path, items,
                                                    telemetry=prior, run_id=f"{repo.name}-kr")
                green_res, bad_res = results
                self.assertEqual(green_res["outcome"], "kept")
                self.assertEqual(bad_res["outcome"], "reverted")
                promoted = [p for r in results for p in r["promoted"]]
                self.assertNotIn("bad.txt", promoted)
                self.assertFalse((repo.path / "bad.txt").exists())  # non-green never reaches the tree

    def test_measured_precision_matches_ground_truth_and_clears_floor(self) -> None:
        lv = _driver()
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            for repo in qb_corpus.build_corpus(base / "corpus"):
                prior = self._eligible_telemetry(lv, repo, base)
                a2 = lv.run_campaign(repo, "A2", base / "a2" / repo.name / "QB-Audit",
                                     prior_telemetry=prior)
                measured = a2.telemetry["quality"]["precision_estimate"]
                # Ground truth: the single fixable finding is a true positive that
                # verifies green, so measured precision is 1.0 within tolerance.
                self.assertAlmostEqual(measured, 1.0, delta=0.001)
                self.assertGreaterEqual(measured, lv._telemetry.PRECISION_FLOOR)
                self.assertTrue(a2.telemetry["quality"]["fix_safety_ok"])

    def test_promotion_confined_to_allowlist_and_repo_root(self) -> None:
        # The sole working-tree write path (_promote) stays within the policy write
        # allowlist and repo_root; an out-of-allowlist byproduct is never promoted.
        lv = _driver()
        orch = lv._budget._orch
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            for repo in qb_corpus.build_corpus(base / "corpus"):
                iso = orch._isolation.Isolation(
                    repo.path, level="A2", run_id="allow", allowlist=["*.txt"]).open()
                try:
                    (iso.worktree_path / "ok.txt").write_text("fine\n", encoding="utf-8")
                    (iso.worktree_path / "evil.py").write_text("x = 1\n", encoding="utf-8")
                    promoted = orch._promote(iso, repo.path)
                    self.assertIn("ok.txt", promoted)
                    self.assertNotIn("evil.py", promoted)
                    self.assertTrue((repo.path / "ok.txt").is_file())       # allowlisted: promoted
                    self.assertFalse((repo.path / "evil.py").exists())      # filtered: not written
                finally:
                    iso.teardown()


if __name__ == "__main__":
    unittest.main()
