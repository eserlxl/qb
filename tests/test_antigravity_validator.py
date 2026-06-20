"""Naming-contract regression pin for antigravity's divergent validate_planner_docs.py.

Antigravity ships its own (vibecoding-first, planning-only) validator that is NOT
synced from shared/, so the shared-validator suites do not cover it. This pins the
load-bearing piece -- that its artifact-naming regexes and document H1 heading
constants match QB's house .qb/ convention (the exact thing the upstream Faz/Planing
naming was converted away from) -- so a regression in the divergent copy fails CI.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import ANTIGRAVITY, SHARED_DIR


ANTIGRAVITY_PLANNING_FILES = {
    "skills/qb/SKILL.md",
    "skills/qb/scripts/validate_planner_docs.py",
    "skills/qb/references/first-planner.md",
    "skills/qb/references/assessment-planner.md",
    "skills/qb/references/second-planner.md",
    "skills/qb/references/third-planner.md",
    "skills/qb/references/fourth-planner.md",
    "skills/qb/references/handoffs/run-step2.md",
    "skills/qb/references/handoffs/run-step3.md",
    "skills/qb/references/handoffs/run-step4.md",
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


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # 3.14 dataclasses needs the module registered
    spec.loader.exec_module(module)
    return module


def _evidence_engine_modules() -> list[tuple[str, object]]:
    """(label, module) for every validator carrying the ported evidence-engine gates."""
    mods: list[tuple[str, object]] = []
    shared_path = SHARED_DIR / "scripts/validate_planner_docs.py"
    if shared_path.exists():
        mods.append(("shared", _load_module("shared_vpd_gates", shared_path)))
    anti_path = ANTIGRAVITY["root"] / "skills/qb/scripts/validate_planner_docs.py"
    if anti_path.exists():
        mods.append(("antigravity", _load_module("antigravity_vpd_gates", anti_path)))
    return mods


_VALID_COMPREHENSION = """# Project Comprehension

qb_schema_version: 2

## 1. Understanding Goals and Competency Questions

CQ-01: What entry point starts the primary workflow?

## 2. Evidence Register and Confidence

| Evidence ID | Claim Type | Claim | Evidence source | Evidence type | Confidence | Freshness | Contradiction | Next probe |
|---|---|---|---|---|---|---|---|---|
| EV-01 | structural | api module exists | src/api.py:10 | source | confirmed | fresh | none | none |

## 3. Domain-to-Code Trace Map

NOT_APPLICABLE: trivial single-module script with no distinct domain mapping.

## 4. Structure, Data, and Runtime Flow Model

A single entrypoint calls the request handler directly.

## 5. Intended vs Implemented Architecture

NOT_APPLICABLE: no intended-architecture document exists for this small tool.

## 6. Change History, Hotspots, and Ownership Signals

Low churn with a single owner over the last year.

## 7. Quality Attribute Scenarios and Tradeoffs

Modifiability is prioritized over raw performance for this tool.

## 8. Open Hypotheses and Validation Probes

NO_UNRESOLVED_HYPOTHESES: every recorded claim is confirmed by direct source evidence.
"""


class EvidenceEngineGateTests(unittest.TestCase):
    """Pin the ported markdown-table / comprehension / ontology / readiness / audit-depth gates.

    Each case runs against BOTH the shared validator (the engine-host source of truth)
    and the divergent antigravity validator, since the gate logic is identical in both
    and must not silently regress in either.
    """

    def setUp(self) -> None:
        self.modules = _evidence_engine_modules()
        self.assertTrue(self.modules, "no validator modules with evidence-engine gates were found")

    def _state(self, mod, root, strict: bool = False):
        return mod.ValidationState(root=Path(root), mode="all", strict=strict)

    def _write_qb(self, root, name: str, text: str) -> None:
        qb = Path(root) / ".qb"
        qb.mkdir(parents=True, exist_ok=True)
        (qb / name).write_text(text, encoding="utf-8")

    # --- markdown table parser + evidence helpers ---
    def test_markdown_tables_parses_headers_and_rows(self) -> None:
        section = "| A | B |\n|---|---|\n| 1 | 2 |\n"
        for label, mod in self.modules:
            with self.subTest(validator=label):
                tables = mod.markdown_tables(section)
                self.assertEqual(len(tables), 1)
                headers, rows = tables[0]
                self.assertEqual(headers, ["A", "B"])
                self.assertEqual(rows, [{"A": "1", "B": "2"}])

    def test_cell_has_evidence_rejects_placeholders(self) -> None:
        for label, mod in self.modules:
            with self.subTest(validator=label):
                self.assertTrue(mod.cell_has_evidence("src/api.py:10"))
                for placeholder in ("", "n/a", "none", "unknown", "-"):
                    self.assertFalse(mod.cell_has_evidence(placeholder), placeholder)

    def test_has_independent_evidence_requires_two_types_and_locators(self) -> None:
        for label, mod in self.modules:
            with self.subTest(validator=label):
                self.assertTrue(mod.has_independent_evidence("source, test", "a.py:1, b_test.py:2"))
                self.assertFalse(mod.has_independent_evidence("source", "a.py:1"))

    def test_evidence_is_direct_for_claim(self) -> None:
        for label, mod in self.modules:
            with self.subTest(validator=label):
                self.assertTrue(mod.evidence_is_direct_for_claim("structural", "source", "a.py:1"))
                self.assertFalse(mod.evidence_is_direct_for_claim("structural", "test", "a_test.py:1"))

    # --- optional comprehension doc gate (`.qb/project-comprehension.md`) ---
    def test_comprehension_absent_is_dormant(self) -> None:
        for label, mod in self.modules:
            with self.subTest(validator=label):
                with tempfile.TemporaryDirectory() as tmp:
                    state = self._state(mod, tmp)
                    mod.validate_optional_comprehension_doc(state)
                    self.assertEqual(state.metrics.get("comprehension_exists"), "false")
                    self.assertEqual(state.warnings, [])
                    self.assertEqual(state.errors, [])

    def test_comprehension_valid_has_no_findings(self) -> None:
        for label, mod in self.modules:
            with self.subTest(validator=label):
                with tempfile.TemporaryDirectory() as tmp:
                    self._write_qb(tmp, "project-comprehension.md", _VALID_COMPREHENSION)
                    state = self._state(mod, tmp)
                    mod.validate_optional_comprehension_doc(state)
                    self.assertEqual(state.metrics.get("comprehension_exists"), "true")
                    self.assertEqual(state.warnings, [], f"unexpected warnings: {state.warnings}")
                    self.assertEqual(state.errors, [], f"unexpected errors: {state.errors}")

    def test_comprehension_invalid_claim_type_warns(self) -> None:
        bad = _VALID_COMPREHENSION.replace("| EV-01 | structural |", "| EV-01 | bogus |")
        for label, mod in self.modules:
            with self.subTest(validator=label):
                with tempfile.TemporaryDirectory() as tmp:
                    self._write_qb(tmp, "project-comprehension.md", bad)
                    state = self._state(mod, tmp)
                    mod.validate_optional_comprehension_doc(state)
                    self.assertTrue(any("invalid_claim_type" in w for w in state.warnings), state.warnings)

    def test_comprehension_confirmed_without_evidence_warns(self) -> None:
        bad = _VALID_COMPREHENSION.replace("| src/api.py:10 | source | confirmed |", "| n/a | source | confirmed |")
        for label, mod in self.modules:
            with self.subTest(validator=label):
                with tempfile.TemporaryDirectory() as tmp:
                    self._write_qb(tmp, "project-comprehension.md", bad)
                    state = self._state(mod, tmp)
                    mod.validate_optional_comprehension_doc(state)
                    self.assertTrue(
                        any("high_confidence_without_evidence" in w for w in state.warnings), state.warnings
                    )

    # --- optional ontology competency-question gate (`.qb/project-ontology.md`) ---
    def test_ontology_competency_invalid_status_warns(self) -> None:
        doc = (
            "# Project Ontology\n\n## 8. Competency Questions\n\n"
            "| Question ID | Status | Evidence |\n|---|---|---|\n"
            "| CQ-1 | bogus_status | src/x.py:1 |\n"
        )
        for label, mod in self.modules:
            with self.subTest(validator=label):
                with tempfile.TemporaryDirectory() as tmp:
                    self._write_qb(tmp, "project-ontology.md", doc)
                    state = self._state(mod, tmp)
                    mod.validate_optional_ontology_doc(state)
                    self.assertEqual(state.metrics.get("ontology_exists"), "true")
                    self.assertTrue(
                        any("invalid_ontology_question_status" in w for w in state.warnings), state.warnings
                    )

    def test_ontology_answered_without_evidence_warns(self) -> None:
        doc = (
            "# Project Ontology\n\n## 8. Competency Questions\n\n"
            "| Question ID | Status | Evidence |\n|---|---|---|\n"
            "| CQ-1 | answered | n/a |\n"
        )
        for label, mod in self.modules:
            with self.subTest(validator=label):
                with tempfile.TemporaryDirectory() as tmp:
                    self._write_qb(tmp, "project-ontology.md", doc)
                    state = self._state(mod, tmp)
                    mod.validate_optional_ontology_doc(state)
                    self.assertTrue(
                        any("ontology_question_missing_evidence" in w for w in state.warnings), state.warnings
                    )

    # --- audit-section-depth gate ---
    def test_audit_section_depth_warns_on_headings_only(self) -> None:
        for label, mod in self.modules:
            with self.subTest(validator=label):
                lines = [mod.AUDIT_HEADINGS[0], ""]
                for heading in mod.AUDIT_HEADINGS[1:]:
                    lines += [heading, ""]
                text = "\n".join(lines)
                state = self._state(mod, ".")
                mod.validate_audit_section_depth(text, Path("audit.md"), state)
                self.assertTrue(
                    any("empty_or_too_short_audit_section" in w for w in state.warnings), state.warnings
                )

    def test_audit_section_depth_silent_on_filled_sections(self) -> None:
        body = "This audit section carries more than twenty characters of real content."
        for label, mod in self.modules:
            with self.subTest(validator=label):
                lines = [mod.AUDIT_HEADINGS[0], ""]
                for heading in mod.AUDIT_HEADINGS[1:]:
                    lines += [heading, body]
                text = "\n".join(lines)
                state = self._state(mod, ".")
                mod.validate_audit_section_depth(text, Path("audit.md"), state)
                self.assertEqual([w for w in state.warnings if "empty_or_too_short_audit_section" in w], [])

    # --- Step-4 readiness-row gate ---
    def test_readiness_invalid_status_warns(self) -> None:
        rows = [{"Sub-Plan Path": "p1", "Status": "BOGUS", "Finding IDs": "none", "Dependency State": "satisfied"}]
        for label, mod in self.modules:
            with self.subTest(validator=label):
                state = self._state(mod, ".")
                mod.validate_readiness_rows(rows, Path("audit.md"), state, [])
                self.assertTrue(any("invalid_readiness_status" in w for w in state.warnings), state.warnings)

    def test_readiness_conflicting_status_warns(self) -> None:
        rows = [
            {"Sub-Plan Path": "p1", "Status": "READY", "Finding IDs": "none", "Dependency State": "satisfied"},
            {"Sub-Plan Path": "p1", "Status": "BLOCKED", "Finding IDs": "none", "Dependency State": "blocked"},
        ]
        for label, mod in self.modules:
            with self.subTest(validator=label):
                state = self._state(mod, ".")
                mod.validate_readiness_rows(rows, Path("audit.md"), state, [])
                self.assertTrue(any("conflicting_readiness_status" in w for w in state.warnings), state.warnings)

    def test_readiness_ready_with_blocked_dependency_warns(self) -> None:
        rows = [{"Sub-Plan Path": "p1", "Status": "READY", "Finding IDs": "none", "Dependency State": "blocked"}]
        for label, mod in self.modules:
            with self.subTest(validator=label):
                state = self._state(mod, ".")
                mod.validate_readiness_rows(rows, Path("audit.md"), state, [])
                self.assertTrue(any("ready_row_has_blocked_dependency" in w for w in state.warnings), state.warnings)

    def test_readiness_all_complete_is_no_action_required(self) -> None:
        rows = [
            {"Sub-Plan Path": "p1", "Status": "COMPLETE", "Finding IDs": "none", "Dependency State": "satisfied"},
            {"Sub-Plan Path": "p2", "Status": "COMPLETE", "Finding IDs": "none", "Dependency State": "satisfied"},
        ]
        for label, mod in self.modules:
            with self.subTest(validator=label):
                state = self._state(mod, ".")
                mod.validate_readiness_rows(rows, Path("audit.md"), state, [])
                self.assertEqual(state.metrics.get("readiness_queue_state"), "NO_ACTION_REQUIRED")

    def test_readiness_empty_rows_is_dormant(self) -> None:
        for label, mod in self.modules:
            with self.subTest(validator=label):
                state = self._state(mod, ".")
                mod.validate_readiness_rows([], Path("audit.md"), state, [])
                self.assertEqual(state.warnings, [])
                self.assertNotIn("readiness_queue_state", state.metrics)

    # --- strict-mode promotion (warning -> failure) ---
    def test_strict_mode_promotes_gate_warning_to_failure(self) -> None:
        bad = _VALID_COMPREHENSION.replace("| EV-01 | structural |", "| EV-01 | bogus |")
        for label, mod in self.modules:
            with self.subTest(validator=label):
                with tempfile.TemporaryDirectory() as tmp:
                    self._write_qb(tmp, "project-comprehension.md", bad)
                    state = self._state(mod, tmp, strict=True)
                    mod.validate_optional_comprehension_doc(state)
                    self.assertTrue(state.warnings)
                    with contextlib.redirect_stdout(io.StringIO()):
                        rc = mod.finalize(state)
                    self.assertEqual(rc, 1, "strict mode must fail when a gate warning is present")


if __name__ == "__main__":
    unittest.main()
