"""Phase 3.3 -- verification gate keep/revert + redacted evidence.

Pins: the keep path (green verification keeps the fix); the revert path (non-green
auto-reverts to the rollback handle); the no-command fail-closed rule (never
applied, never kept); timeout -> revert; and secret redaction of captured output.
Runs on a real temp git repo via the Phase-3.2 isolation runtime.
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

GATE_PATH = SHARED_DIR / "scripts/verification_gate.py"
ISO_PATH = SHARED_DIR / "scripts/isolation.py"


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
    (d / "flag.txt").write_text("BAD\n", encoding="utf-8")
    _git(d, "add", "-A")
    _git(d, "commit", "-q", "-m", "init")


# Verification command: green only when flag.txt reads GOOD.
_VERIFY = ["python3", "-c",
           "import pathlib,sys; sys.exit(0 if pathlib.Path('flag.txt').read_text().strip()=='GOOD' else 1)"]


def _plan(command):
    return types.SimpleNamespace(finding=types.SimpleNamespace(id="QBF-000000000000"), verify_command=command)


@unittest.skipIf(subprocess.run(["git", "--version"], capture_output=True).returncode != 0, "git unavailable")
class VerificationGateTests(unittest.TestCase):
    def setUp(self) -> None:
        if not GATE_PATH.exists() or not ISO_PATH.exists():
            self.skipTest("gate or isolation missing")
        self.gate = _load("qb_verification_gate_under_test", GATE_PATH)
        self.iso = _load("qb_isolation_under_test", ISO_PATH)

    def _isolation(self, repo, run_id):
        return self.iso.Isolation(repo, level=self.iso.A1, run_id=run_id).open()

    def test_green_fix_is_kept(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _init_repo(repo)
            isolation = self._isolation(repo, "keep")
            try:
                record = self.gate.gate_fix(
                    isolation, _plan(_VERIFY),
                    apply_fn=lambda iso: iso.write_file("flag.txt", "GOOD\n"),
                )
                self.assertEqual(record.outcome, "kept")
                self.assertEqual(record.after_exit, 0)
                self.assertEqual((isolation.worktree_path / "flag.txt").read_text(), "GOOD\n")
            finally:
                isolation.teardown()

    def test_failing_fix_is_auto_reverted(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _init_repo(repo)
            isolation = self._isolation(repo, "revert")
            try:
                handle = isolation.capture_handle()
                record = self.gate.gate_fix(
                    isolation, _plan(_VERIFY),
                    apply_fn=lambda iso: iso.write_file("flag.txt", "STILL-BAD\n"),
                )
                self.assertEqual(record.outcome, "reverted")
                self.assertNotEqual(record.after_exit, 0)
                # tree reset to the captured handle
                self.assertEqual((isolation.worktree_path / "flag.txt").read_text(), "BAD\n")
                self.assertEqual(isolation.capture_handle(), handle)
            finally:
                isolation.teardown()

    def test_no_command_is_never_applied_or_kept(self) -> None:
        applied = {"called": False}

        def _apply(iso):
            applied["called"] = True

        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _init_repo(repo)
            isolation = self._isolation(repo, "nocmd")
            try:
                record = self.gate.gate_fix(isolation, _plan(None), apply_fn=_apply)
                self.assertEqual(record.outcome, "reverted")
                self.assertEqual(record.reason, "no-verification-command")
                self.assertFalse(applied["called"], "fix must not be applied without a verify command")
            finally:
                isolation.teardown()

    def test_timeout_triggers_revert(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _init_repo(repo)
            isolation = self._isolation(repo, "timeout")
            try:
                record = self.gate.gate_fix(
                    isolation, _plan(["python3", "-c", "import time; time.sleep(10)"]),
                    apply_fn=lambda iso: iso.write_file("flag.txt", "GOOD\n"),
                    timeout=1,
                )
                self.assertEqual(record.outcome, "reverted")
                self.assertEqual((isolation.worktree_path / "flag.txt").read_text(), "BAD\n")
            finally:
                isolation.teardown()

    def test_secret_in_output_is_redacted(self) -> None:
        token_cmd = ["python3", "-c", "print('ghp_' + 'A' * 30); import sys; sys.exit(1)"]
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _init_repo(repo)
            isolation = self._isolation(repo, "redact")
            try:
                record = self.gate.gate_fix(
                    isolation, _plan(token_cmd),
                    apply_fn=lambda iso: iso.write_file("flag.txt", "X\n"),
                )
                self.assertNotIn("ghp_" + "A" * 30, record.after_output)
                self.assertIn("<redacted>", record.after_output)
            finally:
                isolation.teardown()

    def test_minimal_env_drops_secrets_keeps_essentials(self) -> None:
        cs = _load("qb_command_safety_for_gate_test", SHARED_DIR / "scripts/command_safety.py")
        env = cs.minimal_env({"PATH": "/usr/bin", "HOME": "/h", "LC_ALL": "C",
                              "AWS_SECRET_ACCESS_KEY": "x", "MY_API_TOKEN": "y"})
        self.assertEqual(env.get("PATH"), "/usr/bin")
        self.assertEqual(env.get("HOME"), "/h")
        self.assertEqual(env.get("LC_ALL"), "C")
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", env)
        self.assertNotIn("MY_API_TOKEN", env)

    def test_verification_does_not_inherit_secret_env(self) -> None:
        import os
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            os.environ["QB_TEST_FAKE_SECRET"] = "leaked"
            try:
                # Exits 0 only if the secret env var is ABSENT from the child.
                cmd = ["python3", "-c",
                       "import os,sys; sys.exit(1 if 'QB_TEST_FAKE_SECRET' in os.environ else 0)"]
                code, out = self.gate.run_verification(cmd, cwd=repo)
                self.assertEqual(code, 0, f"secret env leaked into verification child: {out}")
            finally:
                os.environ.pop("QB_TEST_FAKE_SECRET", None)


if __name__ == "__main__":
    unittest.main()
