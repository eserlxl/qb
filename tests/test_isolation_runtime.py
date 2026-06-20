"""Phase 3.2 -- isolation & rollback runtime.

Pins: worktree isolation lifecycle (open/capture/write/restore/teardown) on a real
temp git repo; the clean-tree invariant (the operator's tree is untouched when
nothing is promoted); collision-safe + fail-closed creation; A0 writes nothing;
and the path-allowlist write guard.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

MODULE_PATH = SHARED_DIR / "scripts/isolation.py"


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
    (d / "a.txt").write_text("hello\n", encoding="utf-8")
    _git(d, "add", "-A")
    _git(d, "commit", "-q", "-m", "init")


@unittest.skipIf(subprocess.run(["git", "--version"], capture_output=True).returncode != 0, "git unavailable")
class IsolationRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        if not MODULE_PATH.exists():
            self.skipTest(f"isolation missing: {MODULE_PATH}")
        self.iso = _load("qb_isolation_under_test", MODULE_PATH)

    def test_lifecycle_write_and_restore(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _init_repo(repo)
            isolation = self.iso.Isolation(repo, level=self.iso.A1, run_id="lc").open()
            try:
                handle = isolation.capture_handle()
                self.assertTrue(handle)
                isolation.write_file("a.txt", "changed\n")
                isolation.write_file("new.txt", "added\n")
                self.assertEqual((isolation.worktree_path / "a.txt").read_text(), "changed\n")
                isolation.restore(handle)
                self.assertEqual((isolation.worktree_path / "a.txt").read_text(), "hello\n")
                self.assertFalse((isolation.worktree_path / "new.txt").exists())
            finally:
                isolation.teardown()

    def test_clean_tree_invariant_when_nothing_promoted(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _init_repo(repo)
            with self.iso.Isolation(repo, level=self.iso.A1, run_id="ct") as isolation:
                isolation.write_file("a.txt", "scratch\n")
            # operator tree untouched, no leftover qb-fix branch, worktree gone
            self.assertEqual((repo / "a.txt").read_text(), "hello\n")
            self.assertFalse((repo / "new.txt").exists())
            branches = _git(repo, "branch", "--list", "qb-fix/*").stdout.strip()
            self.assertEqual(branches, "", f"leftover branch: {branches}")

    def test_branch_collision_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _init_repo(repo)
            _git(repo, "branch", "qb-fix/dup")
            with self.assertRaises(self.iso.IsolationError):
                self.iso.Isolation(repo, level=self.iso.A1, run_id="dup").open()

    def test_non_git_target_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(self.iso.IsolationError):
                self.iso.Isolation(Path(d), level=self.iso.A1, run_id="x").open()

    def test_a0_opens_no_isolation_and_refuses_writes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _init_repo(repo)
            isolation = self.iso.Isolation(repo, level=self.iso.A0, run_id="a0").open()
            self.assertFalse(isolation.opened)
            self.assertIsNone(isolation.worktree_path)
            self.assertIsNone(isolation.capture_handle())
            with self.assertRaises(self.iso.IsolationError):
                isolation.write_file("a.txt", "x")

    def test_path_allowlist_write_guard(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _init_repo(repo)
            with self.iso.Isolation(repo, level=self.iso.A1, run_id="guard", allowlist=["src/*"]) as isolation:
                isolation.write_file("src/ok.py", "x = 1\n")
                with self.assertRaises(self.iso.IsolationError):
                    isolation.write_file("evil.py", "x = 1\n")
                with self.assertRaises(ValueError):
                    isolation.write_file("../escape.py", "x = 1\n")
                # A symlink component pointing outside the worktree must also be
                # refused: resolve_within (called before the allowlist) follows the
                # link, so this catches a symlink escape that a textual ../ check
                # alone would miss.
                with tempfile.TemporaryDirectory() as outside:
                    (Path(isolation.worktree_path) / "link").symlink_to(outside)
                    with self.assertRaises(ValueError):
                        isolation.write_file("link/escape.py", "x = 1\n")


if __name__ == "__main__":
    unittest.main()
