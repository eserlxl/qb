"""Phase 4.2 -- autonomy level enforcement (tree-state invariants).

Drives run_finding at each level over a real temp git fixture and asserts the
per-level invariant: A0 no writes/report-only; A1 working tree byte-identical
(isolation only); A2 only verified fixes promoted to the working tree; A3
changeset assembled only when explicitly enabled. Plus block-not-warn for an
out-of-policy (above-level / wrong-category) action.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

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
class AutonomyLevelTests(unittest.TestCase):
    def setUp(self) -> None:
        for path in (ORCH_PATH, POLICY_PATH, FIXER_PATH):
            if not path.exists():
                self.skipTest(f"missing module: {path}")
        self.orch = _load("qb_orchestrator_under_test", ORCH_PATH)
        self.policy = _load("qb_policy_under_test", POLICY_PATH)
        self.fixer = _load("qb_fixer_under_test", FIXER_PATH)

    def _quality_finding(self):
        ev = "style.txt:1"
        return self.fixer.Finding(
            id=self.fixer.compute_finding_id("quality", ev, "lint:style"),
            category="quality", severity="P3", confidence="medium",
            evidence=ev, rationale="style", suggested_fix="clean it", fix_strategy="propose",
        )

    def _policy(self, level, categories=("quality",)):
        return self.policy.parse_policy({
            "autonomy_level": level,
            "auto_fixable_categories": list(categories),
            "default_min_confidence": "medium",
            "write_allowlist": ["*.txt"],
        })

    # Telemetry whose precision + fix-safety have EARNED auto-apply (A2). Promotion
    # at A2/A3 now requires this; a cold start (telemetry=None) is clamped to A1.
    _EARNED_A2 = {"quality": {"precision_estimate": 0.95, "fix_safety_ok": True}}

    def _run(self, level, repo, apply_value="clean\n", enable_a3=False,
             categories=("quality",), telemetry=None):
        plan = self.fixer.plan_fix(self._quality_finding(), repo)
        return self.orch.run_finding(
            self._policy(level, categories), repo, plan,
            apply_fn=lambda iso: iso.write_file("style.txt", apply_value),
            run_id=level.lower(), enable_a3=enable_a3, telemetry=telemetry,
        )

    def test_a0_reports_and_never_writes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _build_fixture(repo)
            result = self._run("A0", repo)
            self.assertEqual(result["outcome"], "report-only")
            self.assertEqual((repo / "style.txt").read_text(), "messy\n")
            self.assertEqual(_git(repo, "branch", "--list", "qb-fix/*").stdout.strip(), "")

    def test_a1_confines_writes_to_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _build_fixture(repo)
            result = self._run("A1", repo)
            self.assertEqual(result["outcome"], "kept")     # verified green in isolation
            self.assertEqual(result["promoted"], [])        # never promoted
            self.assertEqual((repo / "style.txt").read_text(), "messy\n")  # tree untouched
            self.assertEqual(_git(repo, "branch", "--list", "qb-fix/*").stdout.strip(), "")

    def test_a2_promotes_only_verified_fix(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _build_fixture(repo)
            result = self._run("A2", repo, telemetry=self._EARNED_A2)
            self.assertEqual(result["outcome"], "kept")
            self.assertIn("style.txt", result["promoted"])
            self.assertEqual((repo / "style.txt").read_text(), "clean\n")  # promoted to tree

    def test_a2_does_not_promote_a_failing_fix(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _build_fixture(repo)
            result = self._run("A2", repo, apply_value="still-messy\n", telemetry=self._EARNED_A2)
            self.assertEqual(result["outcome"], "reverted")
            self.assertEqual(result["promoted"], [])
            self.assertEqual((repo / "style.txt").read_text(), "messy\n")  # unchanged

    def test_unearned_autonomy_is_clamped_to_a1(self) -> None:
        # A declared A2 whose telemetry has NOT earned auto-apply promotes nothing:
        # the fix verifies green in isolation (kept) but the working tree is untouched.
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _build_fixture(repo)
            unearned = {"quality": {"precision_estimate": 0.10, "fix_safety_ok": True}}
            result = self._run("A2", repo, telemetry=unearned)
            self.assertEqual(result["outcome"], "kept")
            self.assertEqual(result["promoted"], [])              # clamped: nothing promoted
            self.assertEqual(result["earned_ceiling"], "A1")
            self.assertEqual((repo / "style.txt").read_text(), "messy\n")  # tree untouched

    def test_first_run_with_no_telemetry_is_clamped_to_a1(self) -> None:
        # No telemetry at all (cold start) is fail-closed: A2 declared, A1 effective.
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _build_fixture(repo)
            result = self._run("A2", repo, telemetry=None)
            self.assertEqual(result["outcome"], "kept")
            self.assertEqual(result["promoted"], [])
            self.assertEqual(result["earned_ceiling"], "A1")
            self.assertEqual((repo / "style.txt").read_text(), "messy\n")

    def test_a3_changeset_only_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _build_fixture(repo)
            off = self._run("A3", repo, enable_a3=False, telemetry=self._EARNED_A2)
            self.assertEqual(off["outcome"], "kept")
            self.assertIsNone(off["changeset"])         # default-off: no changeset
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _build_fixture(repo)
            on = self._run("A3", repo, enable_a3=True, telemetry=self._EARNED_A2)
            self.assertIsNotNone(on["changeset"])
            self.assertFalse(on["changeset"]["commit_permitted"])  # commit still gated by policy

    def test_above_policy_action_is_blocked_not_warned(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _build_fixture(repo)
            # quality not in the auto-fixable set => blocked, no side effect
            result = self._run("A2", repo, categories=("secret",))
            self.assertEqual(result["outcome"], "blocked")
            self.assertEqual(result["reason"], "category-not-auto-fixable")
            self.assertEqual((repo / "style.txt").read_text(), "messy\n")
            self.assertEqual(_git(repo, "branch", "--list", "qb-fix/*").stdout.strip(), "")

    def test_promote_applies_delete_rename_and_binary(self) -> None:
        # _promote must mirror the full changeset shape, not just in-place text edits.
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _build_fixture(repo)
            (repo / "data.bin").write_bytes(b"\x00\x01\x02")
            (repo / "old.txt").write_text("o\n", encoding="utf-8")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "more")
            iso = self.orch._isolation.Isolation(repo, level="A2", run_id="promo", allowlist=None).open()
            try:
                wt = iso.worktree_path
                (wt / "style.txt").unlink()                          # deletion
                (wt / "old.txt").rename(wt / "new.txt")             # rename
                (wt / "data.bin").write_bytes(b"\xff\xfe\xfd\x00")  # binary modify
                promoted = self.orch._promote(iso, repo)
                self.assertFalse((repo / "style.txt").exists())     # deletion applied
                self.assertFalse((repo / "old.txt").exists())       # rename: old removed
                self.assertTrue((repo / "new.txt").is_file())       # rename: new added
                self.assertEqual((repo / "data.bin").read_bytes(), b"\xff\xfe\xfd\x00")  # binary intact
                self.assertEqual(set(promoted), {"style.txt", "old.txt", "new.txt", "data.bin"})
            finally:
                iso.teardown()

    def test_promote_skips_out_of_allowlist_path(self) -> None:
        # A change outside the write allowlist (a policy violation, or an incidental
        # verification byproduct) is filtered out -- never written to the real tree.
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _build_fixture(repo)
            iso = self.orch._isolation.Isolation(repo, level="A2", run_id="deny", allowlist=["*.txt"]).open()
            try:
                (iso.worktree_path / "evil.py").write_text("x = 1\n", encoding="utf-8")
                (iso.worktree_path / "ok.txt").write_text("fine\n", encoding="utf-8")
                promoted = self.orch._promote(iso, repo)
                self.assertNotIn("evil.py", promoted)
                self.assertFalse((repo / "evil.py").exists())   # filtered: not written
                self.assertIn("ok.txt", promoted)
                self.assertTrue((repo / "ok.txt").is_file())    # allowlisted: promoted
            finally:
                iso.teardown()


if __name__ == "__main__":
    unittest.main()
