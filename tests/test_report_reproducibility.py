"""Phase 5.3 -- reproducibility, provenance, and cross-review integration.

Pins: the report re-renders byte-identically from the same store except for the
enumerated non-deterministic field (provenance.timing); the provenance block
carries per-analyzer versions, the resolved policy, autonomy level, and budgets,
degrading gracefully for an absent networked analyzer; and a seeded-bad-fix
rejected by the separable reviewer is recorded in the report.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

REPORT_PATH = SHARED_DIR / "scripts/report.py"
STORE_PATH = SHARED_DIR / "scripts/run_store.py"
POLICY_PATH = SHARED_DIR / "scripts/policy.py"
REVIEW_PATH = SHARED_DIR / "scripts/review.py"
SCHEMA_PATH = SHARED_DIR / "scripts/finding_schema.py"


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class ReportReproducibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        for path in (REPORT_PATH, STORE_PATH, POLICY_PATH, REVIEW_PATH, SCHEMA_PATH):
            if not path.exists():
                self.skipTest("phase-5 modules missing")
        self.report = _load("qb_report_under_test", REPORT_PATH)
        self.rs = _load("qb_run_store_under_test", STORE_PATH)
        self.policy = _load("qb_policy_under_test", POLICY_PATH)
        self.review = _load("qb_review_under_test", REVIEW_PATH)
        self.schema = _load("qb_finding_schema_for_repro_test", SCHEMA_PATH)

    def _store(self, root):
        store = self.rs.RunStore(root).open()
        ev = "src/app.py:3"
        f = self.schema.Finding(
            id=self.schema.compute_finding_id("secret", ev, "k"),
            category="secret", severity="P1", confidence="high",
            evidence=ev, rationale="secret-like match", suggested_fix="rotate", fix_strategy="manual")
        store.write_findings([f])
        store.write_summary({"trigger": "completed"})
        return store, f

    def _policy(self):
        return self.policy.parse_policy({
            "autonomy_level": "A2", "auto_fixable_categories": ["quality"],
            "default_min_confidence": "medium", "write_allowlist": ["*.txt"],
            "budgets": {"max_fixes": 5}})

    def test_report_reproducible_except_timing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            store, _ = self._store(Path(d) / self.rs.OUTPUT_DIR_NAME)
            policy = self._policy()
            r1 = self.report.render_json(store, provenance=self.report.build_provenance(policy, timing={"t": "one"}))
            r2 = self.report.render_json(store, provenance=self.report.build_provenance(policy, timing={"t": "two"}))

            def strip(report):
                report = copy.deepcopy(report)
                report.get("provenance", {}).pop("timing", None)
                return json.dumps(report, sort_keys=True)

            self.assertEqual(strip(r1), strip(r2))                  # byte-identical sans timing
            self.assertNotEqual(r1["provenance"]["timing"], r2["provenance"]["timing"])

    def test_provenance_block_contents_and_degradation(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            store, _ = self._store(Path(d) / self.rs.OUTPUT_DIR_NAME)
            policy = self._policy()
            prov = self.report.build_provenance(
                policy, analyzer_versions={"secret-hygiene": "1.0", "dependency-cve": "absent"})
            report = self.report.render_json(store, provenance=prov)
            p = report["provenance"]
            self.assertEqual(p["autonomy_level"], "A2")
            self.assertEqual(p["budgets"], {"max_fixes": 5})
            self.assertEqual(p["policy"]["auto_fixable_categories"], ["quality"])
            self.assertEqual(p["analyzer_versions"]["secret-hygiene"], "1.0")
            self.assertEqual(p["analyzer_versions"]["dependency-cve"], "absent")  # graceful degradation

    def test_seeded_bad_fix_rejection_recorded_in_report(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            store, finding = self._store(Path(d) / self.rs.OUTPUT_DIR_NAME)
            # A mattering (security) fix; a distinct reviewer rejects the bad fix.
            decision = self.review.evaluate_review(
                finding, verification_passed=True,
                author_role=self.review.ROLE_FIXER, reviewer_role=self.review.ROLE_REVIEWER,
                reviewer_keep=False)
            self.assertFalse(decision["promote"])
            self.assertEqual(decision["reason"], "cross-review-revert")
            store.record_evidence({
                "finding_id": finding.id, "outcome": "blocked", "rollback_handle": "h",
                "review": {"reviewer_role": self.review.ROLE_REVIEWER,
                           "author_role": self.review.ROLE_FIXER,
                           "keep": False, "reason": decision["reason"]},
            })
            report = self.report.render_json(store)
            hardening = {h["finding_id"]: h for h in report["hardening"]}
            self.assertIn(finding.id, hardening)
            self.assertFalse(hardening[finding.id]["review"]["keep"])           # rejection recorded
            self.assertEqual(hardening[finding.id]["review"]["reason"], "cross-review-revert")
            self.assertNotEqual(hardening[finding.id]["review"]["reviewer_role"],
                                hardening[finding.id]["review"]["author_role"])  # separable reviewer


if __name__ == "__main__":
    unittest.main()
