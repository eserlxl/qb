"""Guard: scripts/install-hooks.sh install / dry-run / uninstall safety contract.

The opt-in pre-push hook is the compensating control for disabled cloud CI (see
RUNBOOK.md and BASELINE.md), so its installer must be provably correct and safe:

* ``--dry-run`` writes nothing and prints the planned install,
* install writes an **executable** ``.git/hooks/pre-push`` whose payload runs the
  gate of record (``make check``),
* ``--uninstall`` removes a hook the installer wrote, and
* the installer only ever writes inside ``.git/hooks/`` -- no push, no network,
  nothing outside the hooks directory.

Every case runs the **real** ``scripts/install-hooks.sh`` against a throwaway git
repo (a temp mirror of the ``scripts/`` layout the script derives its paths from),
so the developer's own ``.git/hooks`` is never touched. Standard library only.
"""

from __future__ import annotations

import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import REPO_ROOT

INSTALLER = REPO_ROOT / "scripts" / "install-hooks.sh"
HOOK_SRC = REPO_ROOT / "scripts" / "hooks" / "pre-push"


class InstallHooksContractTests(unittest.TestCase):
    def setUp(self) -> None:
        for path in (INSTALLER, HOOK_SRC):
            if not path.is_file():
                self.skipTest(f"{path} missing")
        if shutil.which("git") is None:
            self.skipTest("git unavailable")
        self.tmp = Path(tempfile.mkdtemp(prefix="qb-install-hooks-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        # install-hooks.sh derives REPO_ROOT from its own location, so mirror the
        # scripts/install-hooks.sh + scripts/hooks/pre-push layout and init a real
        # .git so a run targets the sandbox, not the developer's repo.
        (self.tmp / "scripts" / "hooks").mkdir(parents=True)
        shutil.copy2(INSTALLER, self.tmp / "scripts" / "install-hooks.sh")
        shutil.copy2(HOOK_SRC, self.tmp / "scripts" / "hooks" / "pre-push")
        subprocess.run(["git", "init", "-q", str(self.tmp)], check=True)
        self.installer = self.tmp / "scripts" / "install-hooks.sh"
        self.hook_dst = self.tmp / ".git" / "hooks" / "pre-push"

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(self.installer), *args],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
        )

    def _hooks_snapshot(self) -> dict:
        hooks = self.tmp / ".git" / "hooks"
        return {
            str(p.name): p.stat().st_mtime_ns
            for p in hooks.glob("*")
            if p.is_file()
        }

    def test_dry_run_writes_nothing(self) -> None:
        before = self._hooks_snapshot()
        proc = self._run("--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("would install", proc.stdout)
        self.assertFalse(self.hook_dst.exists(), "--dry-run must not write the hook")
        self.assertEqual(before, self._hooks_snapshot(), "--dry-run wrote under .git/hooks")

    def test_install_writes_executable_pre_push(self) -> None:
        proc = self._run()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(self.hook_dst.is_file(), "install did not write the pre-push hook")
        mode = self.hook_dst.stat().st_mode
        self.assertTrue(mode & stat.S_IXUSR, "installed hook is not executable")
        # The payload is the gate of record: it must invoke `make ... check`.
        payload = self.hook_dst.read_text(encoding="utf-8")
        self.assertIn("make", payload)
        self.assertIn("check", payload)

    def test_repeated_install_is_idempotent(self) -> None:
        # Re-running the installer is a common operator action (e.g. after pulling an
        # updated hook). A second install must succeed and leave exactly one
        # byte-identical, executable pre-push hook -- never error or duplicate.
        first = self._run()
        self.assertEqual(first.returncode, 0, first.stderr)
        payload_after_first = self.hook_dst.read_bytes()
        second = self._run()
        self.assertEqual(
            second.returncode, 0,
            f"a repeated install must succeed (idempotent): {second.stderr}",
        )
        self.assertTrue(self.hook_dst.is_file(), "hook missing after repeated install")
        self.assertEqual(
            self.hook_dst.read_bytes(), payload_after_first,
            "repeated install must leave the hook byte-identical, not duplicated",
        )
        self.assertTrue(
            self.hook_dst.stat().st_mode & stat.S_IXUSR,
            "hook must stay executable after a repeated install",
        )
        # Exactly one pre-push hook -- no pre-push.1 / backup duplication. (Ignore
        # git's own pre-push.sample default written by `git init`.)
        pre_push_files = sorted(
            p.name for p in (self.tmp / ".git" / "hooks").glob("pre-push*")
            if p.is_file() and not p.name.endswith(".sample")
        )
        self.assertEqual(
            pre_push_files, ["pre-push"],
            f"repeated install must not duplicate the hook: {pre_push_files}",
        )

    def test_uninstall_removes_installed_hook(self) -> None:
        self._run()  # install first
        self.assertTrue(self.hook_dst.is_file(), "precondition: hook installed")
        proc = self._run("--uninstall")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(self.hook_dst.exists(), "--uninstall did not remove the hook")

    def test_install_writes_only_under_git_hooks(self) -> None:
        # Safety contract: the installer touches nothing in the worktree outside
        # .git/. Snapshot every non-.git file and assert it is byte-identical
        # after an install.
        def worktree_state() -> dict:
            state = {}
            for p in self.tmp.rglob("*"):
                if ".git" in p.parts or not p.is_file():
                    continue
                state[str(p.relative_to(self.tmp))] = p.read_bytes()
            return state

        before = worktree_state()
        proc = self._run()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(before, worktree_state(), "installer wrote outside .git/")

    def test_unknown_argument_is_rejected(self) -> None:
        proc = self._run("--bogus")
        self.assertEqual(proc.returncode, 2, "an unknown argument must exit 2 (usage error)")
        self.assertFalse(self.hook_dst.exists(), "a rejected run must write no hook")


if __name__ == "__main__":
    unittest.main()
