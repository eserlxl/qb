"""Phase 7.2 -- rollback drill + release gates.

Pins: whole-run capture/undo on a real temp git repo (clean tree at baseline,
namespaced reversal ref that does not collide with user branches); and the
fail-closed precision + fix-safety release gates and their gate-to-autonomy map.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

GATE_PATH = SHARED_DIR / "scripts/release_gate.py"
TELEMETRY_PATH = SHARED_DIR / "scripts/telemetry.py"


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
    (d / "a.txt").write_text("original\n", encoding="utf-8")
    _git(d, "add", "-A")
    _git(d, "commit", "-q", "-m", "init")


@unittest.skipIf(subprocess.run(["git", "--version"], capture_output=True).returncode != 0, "git unavailable")
class RollbackDrillTests(unittest.TestCase):
    def setUp(self) -> None:
        if not GATE_PATH.exists():
            self.skipTest("release_gate missing")
        self.rg = _load("qb_release_gate_under_test", GATE_PATH)
        self.t = _load("qb_telemetry_under_test", TELEMETRY_PATH)

    def test_full_run_rollback_drill_passes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _init_repo(repo)

            def mutate(r):
                (r / "a.txt").write_text("CHANGED\n", encoding="utf-8")   # modify tracked
                (r / "b.txt").write_text("new file\n", encoding="utf-8")  # add untracked

            self.assertTrue(self.rg.run_rollback_drill(repo, "drill", mutate))
            # tree restored exactly
            self.assertEqual((repo / "a.txt").read_text(), "original\n")
            self.assertFalse((repo / "b.txt").exists())
            self.assertEqual(_git(repo, "status", "--porcelain").stdout.strip(), "")

    def test_reversal_ref_is_namespaced_and_cleaned_up(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _init_repo(repo)
            handle = self.rg.capture_baseline(repo, "ns")
            self.assertTrue(handle["ref"].startswith("refs/qb-baseline/"))
            # not a normal branch -> never collides with user branches
            self.assertEqual(_git(repo, "branch", "--list").stdout.strip(), "* " + _git(repo, "branch", "--show-current").stdout.strip())
            self.rg.release_baseline(repo, handle)
            self.assertNotEqual(_git(repo, "show-ref", handle["ref"]).returncode, 0)

    def _telemetry(self, kept, reverted):
        return self.t.build_telemetry(run_id="r", autonomy_level="A2", findings=[],
                                      evidence=[{"outcome": "kept", "after_exit": 0}] * kept
                                               + [{"outcome": "reverted", "after_exit": 1}] * reverted)

    def test_precision_gate_fail_closed(self) -> None:
        self.assertFalse(self.rg.precision_gate(self._telemetry(0, 0))[0])      # no data
        self.assertTrue(self.rg.precision_gate(self._telemetry(9, 1))[0])       # 0.9 >= 0.8
        self.assertFalse(self.rg.precision_gate(self._telemetry(1, 9))[0])      # 0.1 < 0.8

    def test_fix_safety_gate(self) -> None:
        good = self.t.build_telemetry(run_id="r", autonomy_level="A2", findings=[],
                                      evidence=[{"outcome": "kept", "after_exit": 0}])
        bad = self.t.build_telemetry(run_id="r", autonomy_level="A2", findings=[],
                                     evidence=[{"outcome": "kept", "after_exit": 3}])
        self.assertTrue(self.rg.fix_safety_gate(good)[0])
        self.assertFalse(self.rg.fix_safety_gate(bad)[0])

    def test_permitted_autonomy_mapping(self) -> None:
        self.assertEqual(self.rg.permitted_autonomy(self._telemetry(9, 1)), "A2")
        self.assertEqual(self.rg.permitted_autonomy(self._telemetry(1, 9)), "A1")
        self.assertEqual(self.rg.permitted_autonomy(self._telemetry(0, 0)), "A1")  # fail-closed


if __name__ == "__main__":
    unittest.main()
