"""Naming-contract regression pin for antigravity's divergent validate_planner_docs.py.

Antigravity ships its own (vibecoding-first, planning-only) validator that is NOT
synced from shared/, so the shared-validator suites do not cover it. This pins the
load-bearing piece -- that its artifact-naming regexes and document H1 heading
constants match QB's house .qb/ convention (the exact thing the upstream Faz/Planing
naming was converted away from) -- so a regression in the divergent copy fails CI.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest

from tests.qb_monorepo import ANTIGRAVITY


ANTIGRAVITY_PLANNING_FILES = {
    "skills/qb/SKILL.md",
    "skills/qb/scripts/validate_planner_docs.py",
    "skills/qb/references/first-planner.md",
    "skills/qb/references/assessment-planner.md",
    "skills/qb/references/second-planner.md",
    "skills/qb/references/third-planner.md",
    "skills/qb/references/fourth-planner.md",
    "skills/qb/references/repo-aware-intake.md",
    "skills/qb/references/workflow-quality.md",
    "skills/qb/references/project-comprehension-methods.md",
    "skills/qb/references/vibecoding-principles.md",
    "skills/qb/references/task-delegation-playbook.md",
    "skills/qb/references/planning-ledger.md",
    "skills/qb/references/project-ontology.md",
    "skills/qb/references/assessment-and-budget.md",
    "skills/qb/references/engineering-principles.md",
    "skills/qb/references/probe-policy.md",
    "README.md",
    "CHANGELOG.md",
    "docs/INSTALLATION.md",
    "docs/USAGE.md",
    "docs/MAINTAINING.md",
    "Makefile",
    "scripts/install.sh",
    "LICENSE",
}

ANTIGRAVITY_ENGINE_FILE_NAMES = {
    "audit_runner.py",
    "fixer.py",
    "orchestrator.py",
    "production_gate.py",
    "release_gate.py",
    "verification_gate.py",
}


def _load_validator():
    path = ANTIGRAVITY["root"] / "skills/qb/scripts/validate_planner_docs.py"
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location("antigravity_validate_planner_docs", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # 3.14 dataclasses needs the module registered
    spec.loader.exec_module(module)
    return module


class AntigravityValidatorNamingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = _load_validator()
        if cls.mod is None:
            raise unittest.SkipTest("antigravity not built yet")

    def test_phase_folder_regex_accepts_house_naming_and_rejects_legacy(self) -> None:
        self.assertTrue(self.mod.FOLDER_RE.match("phase-1-plans"))
        self.assertTrue(self.mod.FOLDER_RE.match("phase-12-plans"))
        self.assertIsNone(self.mod.FOLDER_RE.match("phase-1-Plans"))  # legacy capital P
        self.assertIsNone(self.mod.FOLDER_RE.match("Faz-1-Plans"))

    def test_subplan_regex_accepts_house_naming_and_rejects_legacy(self) -> None:
        self.assertTrue(self.mod.SUBPLAN_RE.match("phase-1.1-ci-gate-parity.md"))
        self.assertTrue(self.mod.SUBPLAN_RE.match("phase-2.10-foo.md"))
        self.assertIsNone(self.mod.SUBPLAN_RE.match("Phase1.1-foo.md"))  # legacy
        self.assertIsNone(self.mod.SUBPLAN_RE.match("Faz1.1-foo.md"))

    def test_document_h1_headings_use_house_spelling(self) -> None:
        self.assertEqual(self.mod.STEP1_HEADINGS[0], "# Main Planning")
        self.assertEqual(self.mod.ASSESSMENT_HEADINGS[0], "# Project Assessment")
        self.assertEqual(self.mod.INDEX_HEADINGS[0], "# Sub-Planning Index")
        self.assertEqual(self.mod.AUDIT_HEADINGS[0], "# Sub-Planning Audit")
        self.assertEqual(self.mod.LEDGER_HEADINGS[0], "# Planning Ledger")
        self.assertEqual(self.mod.ONTOLOGY_HEADINGS[0], "# Project Ontology")


class AntigravityPlanningOnlyFileSetTests(unittest.TestCase):
    """Pin antigravity as a planning-only package, not a copied engine build."""

    def test_planning_components_are_present_and_engine_modules_are_absent(self) -> None:
        root = ANTIGRAVITY["root"]
        if not root.exists():
            self.skipTest("antigravity platform not built yet")

        present = {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        }
        self.assertEqual(sorted(ANTIGRAVITY_PLANNING_FILES - present), [])

        # Governed reference inventory: the on-disk references must EXACTLY match
        # the recorded inventory (not merely be a superset of it), so a reference
        # doc added or removed without updating this inventory -- and classifying it
        # in platforms/PARITY.md -- fails the gate rather than drifting silently.
        on_disk_refs = {
            rel for rel in present
            if rel.startswith("skills/qb/references/") and rel.endswith(".md")
        }
        recorded_refs = {
            rel for rel in ANTIGRAVITY_PLANNING_FILES
            if rel.startswith("skills/qb/references/")
        }
        self.assertEqual(
            on_disk_refs, recorded_refs,
            "on-disk Antigravity references diverge from the recorded inventory; "
            "add the doc to ANTIGRAVITY_PLANNING_FILES and classify it in platforms/PARITY.md",
        )

        forbidden = sorted(
            rel
            for rel in present
            if rel.split("/")[-1] in ANTIGRAVITY_ENGINE_FILE_NAMES
            or rel.split("/")[-1].startswith("analyzer_")
        )
        self.assertEqual(forbidden, [])


if __name__ == "__main__":
    unittest.main()
