"""Conformance test for the frozen QB Finding schema (Phase 1.1).

The Finding schema is canonical host-neutral IP under
``shared/scripts/finding_schema.py``. It is the contract every QB analyzer
(Phase 2) and the fixer (Phase 3) must emit and consume, so a malformed finding
must be rejected mechanically before any analyzer logic exists.

This test pins:
- the eight-field record and its required/non-empty fields;
- the four closed vocabularies (category, severity P0-P3, confidence, fix-strategy);
- the ``path:line`` (or ``path:start-end``) evidence locator;
- the deterministic, rerun-stable identity rule;
- the standard-library-only, deterministically-ordered serialization.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import unittest

from tests.qb_monorepo import SHARED_DIR

MODULE_PATH = SHARED_DIR / "scripts/finding_schema.py"


def _load():
    spec = importlib.util.spec_from_file_location("qb_finding_schema_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    # Register before exec so any @dataclass type resolution succeeds.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _valid_kwargs(mod):
    evidence = "shared/scripts/validate_planner_docs.py:114"
    return {
        "id": mod.compute_finding_id("secret", evidence, "hardcoded-openai-key"),
        "category": "secret",
        "severity": "P1",
        "confidence": "high",
        "evidence": evidence,
        "rationale": "A length-bounded token pattern matched at this location.",
        "suggested_fix": "Remove the literal and read the value from the environment.",
        "fix_strategy": "manual",
    }


class FindingSchemaConformanceTests(unittest.TestCase):
    def setUp(self) -> None:
        if not MODULE_PATH.exists():
            self.skipTest(f"finding schema module missing: {MODULE_PATH}")
        self.mod = _load()

    # --- the eight required fields exist -----------------------------------
    def test_finding_has_exactly_the_eight_named_fields(self) -> None:
        import dataclasses

        names = {f.name for f in dataclasses.fields(self.mod.Finding)}
        self.assertEqual(
            names,
            {"id", "category", "severity", "confidence", "evidence",
             "rationale", "suggested_fix", "fix_strategy"},
        )

    # --- closed vocabularies are non-empty frozen sets ---------------------
    def test_closed_vocabularies_are_frozen_and_nonempty(self) -> None:
        self.assertEqual(tuple(self.mod.SEVERITIES), ("P0", "P1", "P2", "P3"))
        for name in ("CATEGORIES", "CONFIDENCE_BANDS", "FIX_STRATEGIES"):
            vocab = getattr(self.mod, name)
            self.assertTrue(vocab, f"{name} is empty")
            self.assertIsInstance(vocab, frozenset)

    # --- a well-formed finding is accepted ---------------------------------
    def test_well_formed_finding_is_accepted(self) -> None:
        finding = self.mod.Finding(**_valid_kwargs(self.mod))
        self.assertEqual(self.mod.validate_finding(finding), [])

    # --- each malformed shape is rejected ----------------------------------
    def test_missing_required_field_is_rejected(self) -> None:
        kwargs = _valid_kwargs(self.mod)
        kwargs["rationale"] = ""  # blank required field
        errors = self.mod.validate_finding(self.mod.Finding(**kwargs))
        self.assertTrue(any("rationale" in e for e in errors), errors)

    def test_out_of_vocabulary_severity_is_rejected(self) -> None:
        kwargs = _valid_kwargs(self.mod)
        kwargs["severity"] = "P9"
        errors = self.mod.validate_finding(self.mod.Finding(**kwargs))
        self.assertTrue(any("severity" in e for e in errors), errors)

    def test_out_of_vocabulary_category_is_rejected(self) -> None:
        kwargs = _valid_kwargs(self.mod)
        kwargs["category"] = "not-a-real-category"
        errors = self.mod.validate_finding(self.mod.Finding(**kwargs))
        self.assertTrue(any("category" in e for e in errors), errors)

    def test_evidence_without_a_location_is_rejected(self) -> None:
        kwargs = _valid_kwargs(self.mod)
        kwargs["evidence"] = "shared/scripts/validate_planner_docs.py"  # no :line
        errors = self.mod.validate_finding(self.mod.Finding(**kwargs))
        self.assertTrue(any("evidence" in e for e in errors), errors)

    def test_line_range_evidence_is_accepted(self) -> None:
        kwargs = _valid_kwargs(self.mod)
        kwargs["evidence"] = "shared/scripts/validate_planner_docs.py:113-120"
        kwargs["id"] = self.mod.compute_finding_id(
            kwargs["category"], kwargs["evidence"], "hardcoded-openai-key"
        )
        self.assertEqual(self.mod.validate_finding(self.mod.Finding(**kwargs)), [])

    def test_evidence_path_with_spaces_is_accepted(self) -> None:
        # A repo-relative path can contain spaces ("dir with space/file.py"); the
        # analyzers build evidence as f"{rel}:{line}" directly from that path, so the
        # schema must accept it -- the trailing ":line" keeps the locator unambiguous.
        kwargs = _valid_kwargs(self.mod)
        kwargs["evidence"] = "dir with space/file.py:10"
        kwargs["id"] = self.mod.compute_finding_id(
            kwargs["category"], kwargs["evidence"], "hardcoded-openai-key"
        )
        self.assertEqual(self.mod.validate_finding(self.mod.Finding(**kwargs)), [])

    def test_evidence_path_with_spaces_and_range_is_accepted(self) -> None:
        kwargs = _valid_kwargs(self.mod)
        kwargs["evidence"] = "a b/c d/module name.py:113-120"
        kwargs["id"] = self.mod.compute_finding_id(
            kwargs["category"], kwargs["evidence"], "hardcoded-openai-key"
        )
        self.assertEqual(self.mod.validate_finding(self.mod.Finding(**kwargs)), [])

    def test_line_zero_evidence_is_rejected(self) -> None:
        # SARIF region.startLine must be >= 1, so line 0 is non-conformant.
        kwargs = _valid_kwargs(self.mod)
        kwargs["evidence"] = "shared/scripts/validate_planner_docs.py:0"
        errors = self.mod.validate_finding(self.mod.Finding(**kwargs))
        self.assertTrue(any("evidence" in e for e in errors), errors)

    def test_inverted_line_range_is_rejected(self) -> None:
        kwargs = _valid_kwargs(self.mod)
        kwargs["evidence"] = "shared/scripts/validate_planner_docs.py:20-5"
        errors = self.mod.validate_finding(self.mod.Finding(**kwargs))
        self.assertTrue(any("evidence" in e for e in errors), errors)

    # --- deterministic identity --------------------------------------------
    def test_identity_is_deterministic_and_location_sensitive(self) -> None:
        a1 = self.mod.compute_finding_id("secret", "config/app.py:42", "hardcoded-secret")
        a2 = self.mod.compute_finding_id("secret", "config/app.py:42", "hardcoded-secret")
        b = self.mod.compute_finding_id("secret", "config/app.py:43", "hardcoded-secret")
        self.assertEqual(a1, a2, "same inputs must produce the same id")
        self.assertNotEqual(a1, b, "different location must produce a different id")
        self.assertRegex(a1, r"^QBF-[0-9a-f]{12}$")

    # --- serialization is std-lib and deterministically ordered ------------
    def test_serialization_is_deterministic_and_stdlib_json(self) -> None:
        finding = self.mod.Finding(**_valid_kwargs(self.mod))
        s1 = self.mod.serialize_finding(finding)
        s2 = self.mod.serialize_finding(finding)
        self.assertEqual(s1, s2, "serialization must be stable across calls")
        parsed = json.loads(s1)  # must be valid JSON (std-lib only)
        self.assertEqual(parsed["fix-strategy"], "manual")  # hyphenated on-disk key
        # keys are emitted in sorted (canonical) order
        self.assertEqual(list(parsed.keys()), sorted(parsed.keys()))
        self.assertNotIn("\n", s1, "a serialized finding is a single line for JSONL")


if __name__ == "__main__":
    unittest.main()
