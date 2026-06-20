"""M7 release-gating procedure consistency (roadmap Phase 6 consolidation).

Pins the consolidated M7-eligible-release procedure (RUNBOOK.md ``### M7-eligible
release``, cross-referenced from RELEASING.md) to the engine so the documented gate
cannot silently drift from the code: it must name every
``production_gate.PRODUCTION_GATE_CHECKS`` conjunct and reference the Phase 6.1 M7
readiness checklist. A renamed/dropped conjunct, or a procedure that loses the
readiness-checklist binding, fails the test instead of leaving a green-but-wrong
procedure.
"""

from __future__ import annotations

import sys
import unittest

from tests.qb_monorepo import REPO_ROOT, SHARED_DIR

RUNBOOK = REPO_ROOT / "RUNBOOK.md"
RELEASING = REPO_ROOT / "RELEASING.md"
SECTION_HEADING = "### M7-eligible release"


def _engine(module_name: str):
    scripts_dir = str(SHARED_DIR / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    return __import__(module_name)


def _load_production_gate():
    return _engine("production_gate")


def _m7_section() -> str:
    text = RUNBOOK.read_text(encoding="utf-8")
    start = text.index(SECTION_HEADING)
    rest = text[start + len(SECTION_HEADING):]
    end = rest.find("\n## ")  # stop at the next top-level section
    return rest if end < 0 else rest[:end]


class M7ReleaseGatingProcedureTests(unittest.TestCase):
    def setUp(self) -> None:
        for path in (RUNBOOK, RELEASING):
            if not path.exists():
                self.skipTest(f"{path.name} missing")
        self.section = _m7_section()

    def test_procedure_names_every_production_gate_conjunct(self) -> None:
        pg = _load_production_gate()
        self.assertTrue(pg.PRODUCTION_GATE_CHECKS)
        for conjunct in pg.PRODUCTION_GATE_CHECKS:
            self.assertIn(
                conjunct, self.section,
                f"the M7-eligible release procedure omits conjunct {conjunct!r}",
            )

    def test_procedure_references_the_readiness_checklist(self) -> None:
        self.assertIn(
            "M7 readiness checklist", self.section,
            "the M7 release procedure must reference the Phase 6.1 readiness checklist",
        )
        releasing = RELEASING.read_text(encoding="utf-8")
        self.assertIn(
            "M7-eligible release", releasing,
            "RELEASING.md must cross-reference the M7-eligible release procedure",
        )

    def test_documented_evidence_filename_matches_engine(self) -> None:
        # The persisted, redacted release-gating decision filename in the procedure
        # must match the engine constant that writes it, so the runbook evidence path
        # cannot drift from release_gate.persist_authorization.
        rg = _engine("release_gate")
        self.assertIn(
            rg.AUTHORIZATION_EVIDENCE_FILENAME, self.section,
            "M7 procedure must document the persisted release-authorization filename "
            "matching release_gate.AUTHORIZATION_EVIDENCE_FILENAME",
        )
        self.assertIn("persist_authorization", self.section)

    def test_procedure_states_fail_closed_and_no_a3_default(self) -> None:
        # Operators must not read a passing gate as authorizing auto-delivery: the
        # procedure states release eligibility fails closed and that passing the gate
        # authorizes operation only -- never A3 auto-delivery -- pinned to the engine
        # constant A3_DEFAULT_ENABLED == False.
        lowered = self.section.lower()
        self.assertIn("fails closed", lowered)
        self.assertIn("operation only", lowered)
        self.assertIn("A3_DEFAULT_ENABLED", self.section)
        pg = _load_production_gate()
        self.assertFalse(pg.A3_DEFAULT_ENABLED,
                         "A3_DEFAULT_ENABLED must be False so a passing gate never auto-delivers")


if __name__ == "__main__":
    unittest.main()
