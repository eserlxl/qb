"""Phase 6.1 -- findings-to-plan projector conformance.

Projects a finding for every finding_schema.CATEGORIES value and every
FIX_STRATEGIES value through findings_to_plan and asserts the projected item is
lint-clean (validate_planwright_plan.validate_plan reports zero errors), preserves
severity and the path:line evidence, infers repair vs improve correctly, carries the
anchor + existing Surface for repair, and never names a Surface under .qb/ or
.planwright/ (planning-state findings are not emitted at all).
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR


def _load(name: str, filename: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SHARED_DIR / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


fs = _load("qb_finding_schema", "finding_schema.py")
ftp = _load("qb_findings_to_plan", "findings_to_plan.py")
vpp = _load("qb_validate_planwright_plan", "validate_planwright_plan.py")


def _finding(category="quality", severity="P2", fix_strategy="manual", evidence="src/app.py:2"):
    return fs.Finding(
        id=fs.compute_finding_id(category, evidence, f"{category}-{fix_strategy}"),
        category=category, severity=severity, confidence="medium",
        evidence=evidence,
        rationale=f"a {category} issue at {evidence} needs attention",
        suggested_fix=f"address the {category} issue at the cited site",
        fix_strategy=fix_strategy)


class FindingsToPlanConformanceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "src").mkdir()
        (self.root / "src/app.py").write_text(
            "\n".join(f"line {i}" for i in range(1, 21)), encoding="utf-8")

    def _errors(self, text):
        errors, _advisories, _count = vpp.validate_plan(text, str(self.root))
        return errors

    def test_every_category_projects_lint_clean(self):
        for category in sorted(fs.CATEGORIES):
            with self.subTest(category=category):
                f = _finding(category=category)
                text = ftp.project_finding(f, str(self.root))
                self.assertIsNotNone(text, f"{category} not projected")
                self.assertEqual(self._errors(text), [], f"{category} lint errors")
                self.assertIn(f.severity, text)     # severity preserved
                self.assertIn(f.evidence, text)     # path:line evidence preserved

    def test_every_fix_strategy_projects_lint_clean_with_correct_mode(self):
        expected = {"autofix": "repair", "propose": "repair",
                    "manual": "repair", "none": "improve"}
        for strat in sorted(fs.FIX_STRATEGIES):
            with self.subTest(fix_strategy=strat):
                f = _finding(fix_strategy=strat)
                text = ftp.project_finding(f, str(self.root))
                self.assertIsNotNone(text)
                self.assertEqual(self._errors(text), [])
                self.assertIn(f"Mode: {expected[strat]}", text)

    def test_repair_item_carries_anchor_and_existing_surface(self):
        f = _finding(fix_strategy="manual", evidence="src/app.py:3")
        text = ftp.project_finding(f, str(self.root))
        self.assertIn("Mode: repair", text)
        self.assertIn("src/app.py:3", text)             # path:line anchor preserved
        self.assertIn("Surfaces: src/app.py", text)     # anchored file is the Surface
        self.assertEqual(self._errors(text), [])

    def test_unresolvable_anchor_falls_back_to_improve(self):
        # A defect strategy whose anchor does not resolve to an existing file is not
        # projectable as a Surface, so it is skipped (no invalid item is emitted).
        f = _finding(fix_strategy="manual", evidence="src/missing.py:2")
        self.assertIsNone(ftp.project_finding(f, str(self.root)))

    def test_planning_state_findings_are_not_emitted(self):
        for ev in (".qb/main-planning.md:1", ".planwright/plan.md:1"):
            with self.subTest(evidence=ev):
                f = _finding(category="config", evidence=ev)
                self.assertIsNone(ftp.project_finding(f, str(self.root)))

    def test_batch_projection_has_no_planning_state_surface_and_is_clean(self):
        findings = [_finding(category=c) for c in sorted(fs.CATEGORIES)]
        findings.append(_finding(category="config", evidence=".qb/x.md:1"))   # skipped
        text = ftp.project_findings(findings, str(self.root))
        self.assertEqual(text.count("- [ ]"), len(fs.CATEGORIES))  # .qb one dropped
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("Surfaces:") or s.startswith("New Surfaces:"):
                self.assertNotIn(".qb/", s)
                self.assertNotIn(".planwright/", s)
        self.assertEqual(self._errors(text), [])


    def test_skipped_planning_state_finding_is_reported(self):
        # A .qb/-anchored finding is dropped, but the drop is reported via `skipped`,
        # never silently lost.
        emitted = _finding(category="quality")
        dropped = _finding(category="config", evidence=".qb/main-planning.md:1")
        skipped = []
        text = ftp.project_findings([emitted, dropped], str(self.root), skipped=skipped)
        self.assertEqual(text.count("- [ ]"), 1)        # only the projectable finding
        self.assertEqual(len(skipped), 1)               # the drop is reported, not silent
        finding, reason = skipped[0]
        self.assertEqual(finding.id, dropped.id)
        self.assertIn("planning state", reason)


if __name__ == "__main__":
    unittest.main()
