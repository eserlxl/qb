"""Phase 3.1 -- finding-to-fix-plan binding contract.

Pins: every Finding category resolves to a recipe; no auto-fixable category lacks
a derivable verify command (auto requires a verify command + confidence floor);
verify commands are argv lists (no shell strings); secrets/injection/etc. are
propose-only; determinism; and the contract performs no writes.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

MODULE_PATH = SHARED_DIR / "scripts/fixer.py"
SCHEMA_PATH = SHARED_DIR / "scripts/finding_schema.py"


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _finding(fixer, category, confidence="medium"):
    evidence = "src/x.py:1"
    return fixer.Finding(
        id=fixer.compute_finding_id(category, evidence, "rk"),
        category=category,
        severity="P2",
        confidence=confidence,
        evidence=evidence,
        rationale="example",
        suggested_fix="example fix",
        fix_strategy="manual",
    )


def _repo_with_make(d: Path, targets=("test", "check")):
    body = ".PHONY: " + " ".join(targets) + "\n" + "".join(f"{t}:\n\techo {t}\n" for t in targets)
    (d / "Makefile").write_text(body, encoding="utf-8")


class FixerBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        if not MODULE_PATH.exists():
            self.skipTest(f"fixer missing: {MODULE_PATH}")
        self.fixer = _load("qb_fixer_under_test", MODULE_PATH)
        self.schema = _load("qb_finding_schema_for_fixer_test", SCHEMA_PATH)

    def test_every_category_resolves_to_a_recipe(self) -> None:
        for category in self.schema.CATEGORIES:
            self.assertTrue(self.fixer.bind_recipe(category), f"no recipe for {category}")

    def test_verify_command_prefers_make_test_and_is_argv(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            _repo_with_make(Path(d))
            cmd = self.fixer.select_verify_command(d)
            self.assertEqual(cmd, ["make", "test"])
            self.assertIsInstance(cmd, list)  # argv form, never a shell string

    def test_verify_command_falls_back_to_unittest_then_none(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "tests").mkdir()
            self.assertEqual(self.fixer.select_verify_command(d),
                             ["python3", "-m", "unittest", "discover", "-s", "tests"])
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(self.fixer.select_verify_command(d))

    def test_quality_is_autofix_only_with_verify_command(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            _repo_with_make(Path(d))
            plan = self.fixer.plan_fix(_finding(self.fixer, "quality"), d)
            self.assertEqual(plan.mode, "autofix")
            self.assertEqual(plan.recipe, "lint-autofix")
            self.assertEqual(plan.verify_command, ["make", "test"])
        with tempfile.TemporaryDirectory() as d:  # no Makefile, no tests/ => no command
            plan = self.fixer.plan_fix(_finding(self.fixer, "quality"), d)
            self.assertEqual(plan.mode, "propose")

    def test_low_confidence_quality_is_proposed_even_with_command(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            _repo_with_make(Path(d))
            plan = self.fixer.plan_fix(_finding(self.fixer, "quality", confidence="low"), d)
            self.assertEqual(plan.mode, "propose")

    def test_risky_categories_are_propose_only(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            _repo_with_make(Path(d))
            for category in ("secret", "injection", "path-traversal", "correctness", "dependency"):
                plan = self.fixer.plan_fix(_finding(self.fixer, category, confidence="high"), d)
                self.assertEqual(plan.mode, "propose", f"{category} must be propose-only")

    def test_no_autofixable_category_lacks_a_verify_rule(self) -> None:
        # For every auto-fixable category, a repo with a verify command must yield autofix.
        with tempfile.TemporaryDirectory() as d:
            _repo_with_make(Path(d))
            for category, (auto, floor, _reason) in self.fixer.AUTO_FIXABLE.items():
                if not auto:
                    continue
                plan = self.fixer.plan_fix(_finding(self.fixer, category, confidence=floor), d)
                self.assertEqual(plan.mode, "autofix", f"{category} should autofix with a command")
                self.assertIsNotNone(plan.verify_command)

    def test_plan_is_deterministic_and_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            _repo_with_make(Path(d))
            before = {p.name: p.stat().st_mtime_ns for p in Path(d).iterdir()}
            p1 = self.fixer.plan_fix(_finding(self.fixer, "quality"), d)
            p2 = self.fixer.plan_fix(_finding(self.fixer, "quality"), d)
            after = {p.name: p.stat().st_mtime_ns for p in Path(d).iterdir()}
            self.assertEqual((p1.mode, p1.recipe, p1.verify_command),
                             (p2.mode, p2.recipe, p2.verify_command))
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
