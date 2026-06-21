"""Phase 3.4 -- fix-safety eval: the autonomous-fix release gate.

Drives the full fixer loop end to end -- Phase 3.1 plan_fix -> Phase 3.2 isolation
-> Phase 3.3 gate -- over seeded git fixtures, asserting the two non-negotiable
invariants:
  * KEEP-GREEN: a kept fix leaves the verification command green.
  * CLEAN-REVERT: a rejected fix leaves the tree byte-identical to its pre-attempt
    state and the isolation container torn down.

Fixtures are built in temporary git repos at test time (never a nested repo
tracked inside QB), and verification uses `python3 -m unittest` so there is no
external tool dependency. This harness runs under `make check` / CI and fails
closed if either invariant is violated.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

FIXER_PATH = SHARED_DIR / "scripts/fixer.py"
ISO_PATH = SHARED_DIR / "scripts/isolation.py"
GATE_PATH = SHARED_DIR / "scripts/verification_gate.py"

# Auto-fixable categories this harness provides a positive fixture for.
COVERED_AUTOFIX_CATEGORIES = {"quality"}


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
    """A git repo whose tests/ verify command is red until style.txt reads 'clean'."""
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "QB Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "style.txt").write_text("messy\n", encoding="utf-8")
    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_style.py").write_text(
        "import pathlib, unittest\n"
        "class T(unittest.TestCase):\n"
        "    def test_clean(self):\n"
        "        self.assertEqual(pathlib.Path('style.txt').read_text().strip(), 'clean')\n",
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")


@unittest.skipIf(subprocess.run(["git", "--version"], capture_output=True).returncode != 0, "git unavailable")
class FixSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        for path in (FIXER_PATH, ISO_PATH, GATE_PATH):
            if not path.exists():
                self.skipTest(f"missing engine module: {path}")
        self.fixer = _load("qb_fixer_under_test", FIXER_PATH)
        self.iso = _load("qb_isolation_under_test", ISO_PATH)
        self.gate = _load("qb_verification_gate_under_test", GATE_PATH)

    def _quality_finding(self):
        evidence = "style.txt:1"
        return self.fixer.Finding(
            id=self.fixer.compute_finding_id("quality", evidence, "lint:style"),
            category="quality", severity="P3", confidence="medium",
            evidence=evidence, rationale="style issue", suggested_fix="make it clean",
            fix_strategy="propose",
        )

    def test_every_autofixable_category_has_fixture_coverage(self) -> None:
        autofixable = {c for c, v in self.fixer.AUTO_FIXABLE.items() if v[0]}
        self.assertTrue(
            autofixable <= COVERED_AUTOFIX_CATEGORIES,
            f"auto-fixable categories without a fix-safety fixture: "
            f"{autofixable - COVERED_AUTOFIX_CATEGORIES}",
        )

    def test_keep_green_invariant_positive_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _build_fixture(repo)
            plan = self.fixer.plan_fix(self._quality_finding(), repo)
            self.assertEqual(plan.mode, "autofix")
            self.assertEqual(plan.verify_command, ["python3", "-m", "unittest", "discover", "-s", "tests"])

            isolation = self.iso.Isolation(repo, level=self.iso.A1, run_id="pos").open()
            try:
                record = self.gate.gate_fix(
                    isolation, plan,
                    apply_fn=lambda iso: iso.write_file("style.txt", "clean\n"),
                )
                self.assertEqual(record.outcome, "kept")
                # KEEP-GREEN: re-running the verify command confirms green.
                exit_code, _out = self.gate.run_verification(plan.verify_command, cwd=isolation.worktree_path)
                self.assertEqual(exit_code, 0)
            finally:
                isolation.teardown()

    def test_clean_revert_invariant_negative_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _build_fixture(repo)
            plan = self.fixer.plan_fix(self._quality_finding(), repo)
            isolation = self.iso.Isolation(repo, level=self.iso.A1, run_id="neg").open()
            try:
                handle = isolation.capture_handle()
                record = self.gate.gate_fix(
                    isolation, plan,
                    apply_fn=lambda iso: iso.write_file("style.txt", "still-messy\n"),
                )
                self.assertEqual(record.outcome, "reverted")
                # CLEAN-REVERT: tree back at the captured handle, content restored.
                self.assertEqual(isolation.capture_handle(), handle)
                self.assertEqual((isolation.worktree_path / "style.txt").read_text(), "messy\n")
            finally:
                isolation.teardown()
            # after teardown the operator tree is untouched and no qb-fix branch remains
            self.assertEqual((repo / "style.txt").read_text(), "messy\n")
            self.assertEqual(_git(repo, "branch", "--list", "qb-fix/*").stdout.strip(), "")


@unittest.skipIf(not (SHARED_DIR / "scripts").is_dir(), "shared/scripts missing")
class EngineShellFreeGuard(unittest.TestCase):
    """The shared engine must never spawn a child through a system shell.

    Every external command goes through ``command_safety.run_command``'s argv
    form (``shell=False``). The command-injection analyzer's rule only matches a
    single-line ``subprocess.(...)(...shell=True`` form, so a *multi-line* call
    could slip a ``shell=True`` past it (``run_command``'s own ``Popen`` spans
    several lines). This line-level scan is multi-line-proof and pins the whole
    shared command-execution surface, including ``run_command`` itself.
    """

    def test_no_shell_string_execution_path_in_engine(self) -> None:
        offenders = []
        for path in sorted((SHARED_DIR / "scripts").glob("*.py")):
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                code = line.split("#", 1)[0]
                if re.search(r"shell\s*=\s*True", code) or re.search(r"\bos\.system\s*\(", code):
                    offenders.append(f"{path.name}:{lineno}: {line.strip()}")
        self.assertEqual(
            offenders,
            [],
            "shared engine code must dispatch shell-free (run_command argv form); "
            f"shell-string execution sink(s) found: {offenders}",
        )


if __name__ == "__main__":
    unittest.main()
