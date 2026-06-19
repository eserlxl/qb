"""Schema guard for the planning-skill eval corpus (tests/fixtures/planning-corpus).

Ground-truth fixtures for the planning/comprehension skills, distinct from the
security-analyzer precision corpus. This guard keeps the corpus and its expected
signals well-formed so a future live grading harness has stable inputs. It is a
SHAPE validator only -- it does not run a planning skill or grade real output.

Standard library only, like the rest of the suite.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests.qb_monorepo import REPO_ROOT

CORPUS = REPO_ROOT / "tests/fixtures/planning-corpus"

REQUIRED_FIXTURES = (
    "clean-layered-service",
    "drifted-architecture",
    "distributed-domain-feature",
    "hidden-coupling-signal",
    "stale-ledger",
    "runtime-only-behavior",
    "security-boundary-risk",
)

REQUIRED_KEYS = (
    "id",
    "description",
    "expected_comprehension_signals",
    "expected_trace_ids",
    "expected_architecture_statuses",
    "expected_quality_checks",
)

LIST_KEYS = (
    "expected_comprehension_signals",
    "expected_trace_ids",
    "expected_architecture_statuses",
    "expected_quality_checks",
)

# Architecture-reflexion vocabulary (intended-vs-implemented relation).
ARCHITECTURE_VOCAB = frozenset({"convergent", "divergent", "unmodeled", "uncertain"})


def _expected(fixture: str) -> dict:
    return json.loads((CORPUS / fixture / "expected.json").read_text(encoding="utf-8"))


class PlanningCorpusSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        if not CORPUS.is_dir():
            self.skipTest("planning-corpus fixtures not present")

    def test_all_required_fixtures_present(self) -> None:
        for fixture in REQUIRED_FIXTURES:
            with self.subTest(fixture=fixture):
                self.assertTrue(
                    (CORPUS / fixture / "expected.json").is_file(),
                    f"missing expected.json for fixture {fixture}",
                )

    def test_expected_json_has_required_keys(self) -> None:
        for fixture in REQUIRED_FIXTURES:
            with self.subTest(fixture=fixture):
                missing = sorted(set(REQUIRED_KEYS) - set(_expected(fixture)))
                self.assertEqual(missing, [], f"{fixture}: missing keys {missing}")

    def test_expected_lists_are_nonempty_string_lists(self) -> None:
        for fixture in REQUIRED_FIXTURES:
            data = _expected(fixture)
            for key in LIST_KEYS:
                with self.subTest(fixture=fixture, key=key):
                    value = data.get(key)
                    self.assertIsInstance(value, list, f"{fixture}:{key} is not a list")
                    self.assertTrue(value, f"{fixture}:{key} is empty")
                    self.assertTrue(
                        all(isinstance(item, str) and item.strip() for item in value),
                        f"{fixture}:{key} has non-string/blank items",
                    )

    def test_fixture_id_matches_directory(self) -> None:
        for fixture in REQUIRED_FIXTURES:
            with self.subTest(fixture=fixture):
                self.assertEqual(_expected(fixture).get("id"), fixture)

    def test_each_fixture_has_material_files(self) -> None:
        for fixture in REQUIRED_FIXTURES:
            with self.subTest(fixture=fixture):
                material = [
                    p
                    for p in (CORPUS / fixture).rglob("*")
                    if p.is_file() and p.name != "expected.json"
                ]
                self.assertTrue(material, f"{fixture} has no material files")

    def test_architecture_statuses_use_controlled_vocab(self) -> None:
        for fixture in REQUIRED_FIXTURES:
            statuses = _expected(fixture).get("expected_architecture_statuses", [])
            for status in statuses:
                with self.subTest(fixture=fixture, status=status):
                    self.assertIn(
                        status,
                        ARCHITECTURE_VOCAB,
                        f"{fixture}: architecture status {status!r} not in {sorted(ARCHITECTURE_VOCAB)}",
                    )


if __name__ == "__main__":
    unittest.main()
