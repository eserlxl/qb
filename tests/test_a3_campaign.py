"""Phase 3.4 -- the A3 reviewable-delivery campaign.

A3 assembles a changeset over promoted files ONLY when the explicit ``enable_a3``
flag is set AND the earned ceiling permits promotion. With the flag disabled, or
on a cold start, no changeset is produced. The assembled ``commit_permitted``
reflects policy and QB never executes a commit/push/PR in this seam. Trusted/
neutralized corpus only; untrusted delivery is gated on Phase 1.
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
    return _load_path("qb_live_validate_a3", REPO_ROOT / "scripts" / "live_validate.py")


def _head(repo: Path) -> str:
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()


@unittest.skipIf(subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
                 "git unavailable")
class A3CampaignTests(unittest.TestCase):
    def _eligible(self, lv, repo, base):
        a1 = lv.run_campaign(repo, "A1", base / "a1" / repo.name / ".qb/audit")
        return lv._store.load_prior_telemetry(a1.output_dir)

    def test_a3_changeset_equals_promoted_under_earned_ceiling_and_optin(self) -> None:
        lv = _driver()
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            for repo in qb_corpus.build_corpus(base / "corpus"):
                prior = self._eligible(lv, repo, base)
                run = lv.run_campaign(repo, "A3", base / "a3" / repo.name / ".qb/audit",
                                      prior_telemetry=prior, enable_a3=True)
                changesets = run.changesets()
                self.assertEqual(len(changesets), 1)
                self.assertEqual(changesets[0]["files"], run.promoted())
                self.assertEqual(run.promoted(), ["fix_target.txt"])

    def test_no_changeset_when_enable_a3_disabled(self) -> None:
        lv = _driver()
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            for repo in qb_corpus.build_corpus(base / "corpus"):
                prior = self._eligible(lv, repo, base)
                run = lv.run_campaign(repo, "A3", base / "a3" / repo.name / ".qb/audit",
                                      prior_telemetry=prior, enable_a3=False)
                # A fix is kept and promoted, but delivery is opt-in: no changeset.
                self.assertIn("kept", run.outcomes())
                self.assertEqual(run.changesets(), [])
                for result in run.results:
                    self.assertIsNone(result["changeset"])

    def test_cold_start_a3_denies_delivery(self) -> None:
        lv = _driver()
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            for repo in qb_corpus.build_corpus(base / "corpus"):
                run = lv.run_campaign(repo, "A3", base / "a3" / repo.name / ".qb/audit",
                                      prior_telemetry=None, enable_a3=True)
                for result in run.results:
                    self.assertEqual(result["earned_ceiling"], "A1")
                    self.assertIsNone(result["changeset"])
                self.assertEqual(run.promoted(), [])

    def test_commit_permitted_reflects_policy_and_no_commit_executed(self) -> None:
        lv = _driver()
        policy = lv.session_policy("A3")
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            for repo in qb_corpus.build_corpus(base / "corpus"):
                prior = self._eligible(lv, repo, base)
                head_before = _head(repo.path)
                run = lv.run_campaign(repo, "A3", base / "a3" / repo.name / ".qb/audit",
                                      prior_telemetry=prior, enable_a3=True)
                changesets = run.changesets()
                self.assertEqual(len(changesets), 1)
                self.assertEqual(changesets[0]["commit_permitted"], bool(policy.allow_commit))
                # QB never executes a commit/push/PR in this seam: HEAD is unchanged.
                self.assertEqual(_head(repo.path), head_before)


if __name__ == "__main__":
    unittest.main()
