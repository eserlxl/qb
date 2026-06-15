"""Phase 4.4 -- role separation + cross-review gate.

Pins: the 'it matters' criteria; the verdict-composition truth table (verification
x cross-review -> promote/demote) for a mattering fix; the self-approval block; a
seeded-bad-fix caught by a distinct reviewer; and the orchestrator promotion seam
honoring a review hook (denied review demotes; allowed review promotes).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

REVIEW_PATH = SHARED_DIR / "scripts/review.py"
ORCH_PATH = SHARED_DIR / "scripts/orchestrator.py"
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


def _finding(category="secret", severity="P1"):
    return types.SimpleNamespace(category=category, severity=severity, evidence="x.py:1")


class CrossReviewUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        if not REVIEW_PATH.exists():
            self.skipTest("review missing")
        self.r = _load("qb_review_under_test", REVIEW_PATH)

    def test_matters_criteria(self) -> None:
        self.assertTrue(self.r.requires_cross_review(_finding("secret", "P3")))
        self.assertTrue(self.r.requires_cross_review(_finding("quality", "P1")))
        self.assertFalse(self.r.requires_cross_review(_finding("quality", "P3")))

    def test_truth_table_for_mattering_fix(self) -> None:
        f = _finding("secret", "P1")
        cases = {
            (True, True): True,
            (True, False): False,
            (False, True): False,
            (False, False): False,
        }
        for (verif, keep), expected in cases.items():
            decision = self.r.evaluate_review(
                f, verification_passed=verif, author_role=self.r.ROLE_FIXER,
                reviewer_role=self.r.ROLE_REVIEWER, reviewer_keep=keep)
            self.assertEqual(decision["promote"], expected, f"verif={verif} keep={keep}")

    def test_self_approval_blocked(self) -> None:
        decision = self.r.evaluate_review(
            _finding("secret", "P1"), verification_passed=True,
            author_role=self.r.ROLE_FIXER, reviewer_role=self.r.ROLE_FIXER, reviewer_keep=True)
        self.assertFalse(decision["promote"])
        self.assertEqual(decision["reason"], "self-approval-blocked")

    def test_seeded_bad_fix_caught_by_distinct_reviewer(self) -> None:
        # distinct reviewer returns revert -> not promoted
        decision = self.r.evaluate_review(
            _finding("secret", "P0"), verification_passed=True,
            author_role=self.r.ROLE_FIXER, reviewer_role=self.r.ROLE_REVIEWER, reviewer_keep=False)
        self.assertFalse(decision["promote"])
        self.assertEqual(decision["reason"], "cross-review-revert")

    def test_non_mattering_fix_is_single_gated(self) -> None:
        decision = self.r.evaluate_review(
            _finding("quality", "P3"), verification_passed=True,
            author_role=self.r.ROLE_FIXER, reviewer_role=self.r.ROLE_FIXER, reviewer_keep=False)
        self.assertTrue(decision["promote"])  # verification alone suffices; no reviewer needed


@unittest.skipIf(subprocess.run(["git", "--version"], capture_output=True).returncode != 0, "git unavailable")
class CrossReviewOrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        for path in (REVIEW_PATH, ORCH_PATH, POLICY_PATH, FIXER_PATH):
            if not path.exists():
                self.skipTest(f"missing module: {path}")
        self.r = _load("qb_review_under_test", REVIEW_PATH)
        self.orch = _load("qb_orchestrator_under_test", ORCH_PATH)
        self.policy = _load("qb_policy_under_test", POLICY_PATH)
        self.fixer = _load("qb_fixer_under_test", FIXER_PATH)

    def _fixture(self, repo: Path) -> None:
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@e.com"])
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"])
        (repo / "style.txt").write_text("messy\n", encoding="utf-8")
        (repo / "tests").mkdir()
        (repo / "tests" / "test_style.py").write_text(
            "import pathlib, unittest\n"
            "class T(unittest.TestCase):\n"
            "    def test_clean(self):\n"
            "        self.assertEqual(pathlib.Path('style.txt').read_text().strip(), 'clean')\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(repo), "add", "-A"])
        subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "init"])

    def _plan(self, repo):
        finding = self.fixer.Finding(
            id=self.fixer.compute_finding_id("quality", "style.txt:1", "lint"),
            category="quality", severity="P3", confidence="medium",
            evidence="style.txt:1", rationale="x", suggested_fix="y", fix_strategy="propose")
        return self.fixer.plan_fix(finding, repo)

    def _policy(self):
        return self.policy.parse_policy({
            "autonomy_level": "A2", "auto_fixable_categories": ["quality"],
            "default_min_confidence": "medium", "write_allowlist": ["*.txt"]})

    # Telemetry that has earned A2 auto-apply, so the promotion seam is reachable.
    _EARNED_A2 = {"quality": {"precision_estimate": 0.95, "fix_safety_ok": True}}

    def test_review_denied_demotes_at_promotion_seam(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            self._fixture(repo)
            result = self.orch.run_finding(
                self._policy(), repo, self._plan(repo),
                apply_fn=lambda iso: iso.write_file("style.txt", "clean\n"),
                run_id="rev-deny", telemetry=self._EARNED_A2,
                review=lambda finding: {"promote": False, "reason": "cross-review-revert"})
            self.assertEqual(result["outcome"], "blocked")
            self.assertEqual(result["reason"], "cross-review-revert")
            self.assertEqual((repo / "style.txt").read_text(), "messy\n")  # not promoted

    def test_review_allowed_promotes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            self._fixture(repo)
            hook = self.r.make_promotion_review(
                author_role=self.r.ROLE_FIXER, reviewer_role=self.r.ROLE_REVIEWER,
                reviewer_fn=lambda finding: True)
            result = self.orch.run_finding(
                self._policy(), repo, self._plan(repo),
                apply_fn=lambda iso: iso.write_file("style.txt", "clean\n"),
                run_id="rev-allow", telemetry=self._EARNED_A2, review=hook)
            self.assertEqual(result["outcome"], "kept")
            self.assertIn("style.txt", result["promoted"])
            self.assertEqual((repo / "style.txt").read_text(), "clean\n")


if __name__ == "__main__":
    unittest.main()
