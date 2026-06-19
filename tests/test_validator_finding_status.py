"""Step 4 gate is finding-status aware and heading detection is fence-aware.

Two correctness properties ported from the upstream planner-doc validator:

1. A fix-list finding may carry an optional lifecycle status in the pipe-delimited
   field after its severity ("AUDIT-FIX-NN | PX | <status> | <title>"). Only
   ``open``/``accepted`` findings gate Step 4, so a ``resolved``/``not_applicable``
   P0 no longer holds the gate shut on a re-audit of an in-progress repo. Severity
   *counting* (``count_audit_severities``) stays deliberately status-unaware.
2. Heading/section detection ignores ``## N.`` lines quoted inside code fences, so a
   fenced heading example does not raise a false duplicate/out-of-order error.

Standard library only, like the rest of the suite.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

VALIDATOR_PATH = SHARED_DIR / "scripts/validate_planner_docs.py"
CORE_PATH = SHARED_DIR / "scripts/analyzer_core.py"


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _audit(*rows: str, status: str = "PASS_WITH_WARNINGS") -> str:
    body = "\n".join(rows)
    return (
        f"# Sub-Planning Audit\n\n## 1. Audit Summary\n\noverall audit status: {status}\n\n"
        f"## 13. Prioritized Fix List\n\n{body}\n\n"
        f"## 15. Audit Result\n\nfinal status: {status}\n"
    )


class FindingStatusGateTests(unittest.TestCase):
    def setUp(self) -> None:
        if not VALIDATOR_PATH.exists() or not CORE_PATH.exists():
            self.skipTest("shared validator/core not present")
        _load("qb_analyzer_core", CORE_PATH)
        self.v = _load("qb_validator_finding_status", VALIDATOR_PATH)

    def _blocking(self, text: str) -> dict[str, int]:
        findings = self.v.parse_audit_findings(text)
        core = sys.modules["qb_analyzer_core"]
        return core.count_severities(
            [sev for _id, sev, st in findings if st in self.v.BLOCKING_FINDING_STATUSES]
        )

    def test_missing_status_defaults_to_open(self) -> None:
        findings = self.v.parse_audit_findings(_audit("- AUDIT-FIX-01 | P0 | a real blocker"))
        self.assertEqual(findings, [("AUDIT-FIX-01", "P0", "open")])

    def test_count_audit_severities_stays_status_unaware(self) -> None:
        text = _audit(
            "- AUDIT-FIX-01 | P0 | resolved | already fixed",
            "- AUDIT-FIX-02 | P1 | open | still open",
        )
        self.assertEqual(
            self.v.count_audit_severities(text), {"P0": 1, "P1": 1, "P2": 0, "P3": 0}
        )

    def test_resolved_high_severity_does_not_block(self) -> None:
        self.assertEqual(self._blocking(_audit("- AUDIT-FIX-01 | P0 | resolved | done"))["P0"], 0)

    def test_open_high_severity_blocks(self) -> None:
        self.assertEqual(self._blocking(_audit("- AUDIT-FIX-01 | P0 | open | needs work"))["P0"], 1)

    def test_accepted_high_severity_still_blocks(self) -> None:
        # accepted == a risk knowingly carried forward; it stays visible and gates.
        self.assertEqual(self._blocking(_audit("- AUDIT-FIX-01 | P1 | accepted | carried"))["P1"], 1)

    def test_not_applicable_does_not_block(self) -> None:
        self.assertEqual(
            self._blocking(_audit("- AUDIT-FIX-01 | P0 | not_applicable | n/a after review"))["P0"], 0
        )

    def test_status_word_inside_title_does_not_reclassify(self) -> None:
        # 'resolved' inside the free-text title must not flip an open finding.
        findings = self.v.parse_audit_findings(_audit("- AUDIT-FIX-01 | P0 | fix the resolved-state bug"))
        self.assertEqual(findings[0][2], "open")

    def test_fenced_heading_is_not_a_duplicate(self) -> None:
        text = "\n".join(self.v.STEP1_HEADINGS) + "\n\n```\n## 1. Executive Summary\n```\n"
        state = self.v.ValidationState(root=Path("/tmp"), mode="step1", strict=False)
        self.v.validate_heading_order(text, self.v.STEP1_HEADINGS, Path("main-planning.md"), state)
        self.assertEqual([e for e in state.errors if "duplicate_heading" in e], [])

    def test_real_duplicate_heading_still_detected(self) -> None:
        text = "\n".join(self.v.STEP1_HEADINGS) + "\n\n## 1. Executive Summary\n\nsecond\n"
        state = self.v.ValidationState(root=Path("/tmp"), mode="step1", strict=False)
        self.v.validate_heading_order(text, self.v.STEP1_HEADINGS, Path("main-planning.md"), state)
        self.assertTrue(any("duplicate_heading" in e for e in state.errors))

    def test_balanced_fence_is_masked_with_preserved_offsets(self) -> None:
        raw = "a\n```\n## 1. fake heading\n```\nb\n"
        masked = self.v._mask_fenced_regions(raw)
        self.assertEqual(len(masked), len(raw))  # offsets preserved for body slicing
        self.assertNotIn("## 1. fake heading", masked)  # fenced heading is hidden

    def test_unterminated_fence_is_left_literal(self) -> None:
        # A fence that opens and never closes must not mask the rest of the document.
        raw = "a\n```text\nexample never closed\n## 13. Prioritized Fix List\n"
        masked = self.v._mask_fenced_regions(raw)
        self.assertEqual(len(masked), len(raw))
        self.assertIn("## 13. Prioritized Fix List", masked)

    def test_unterminated_fence_does_not_drop_fix_list_findings(self) -> None:
        # Regression: a dangling code fence before the fix list previously masked the
        # rest of the doc, emptying the section so a real P0 stopped blocking Step 4.
        text = (
            "# Sub-Planning Audit\n\n## 1. Audit Summary\n\n"
            "overall audit status: PASS_WITH_WARNINGS\n\n"
            "```text\nan illustrative block that is never closed\n\n"
            "## 13. Prioritized Fix List\n\n"
            "- AUDIT-FIX-01 | P0 | open | a real blocker\n\n"
            "## 15. Audit Result\n\nfinal status: PASS_WITH_WARNINGS\n"
        )
        self.assertEqual(
            self.v.parse_audit_findings(text), [("AUDIT-FIX-01", "P0", "open")]
        )
        self.assertEqual(self._blocking(text)["P0"], 1)


if __name__ == "__main__":
    unittest.main()
