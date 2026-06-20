"""M7 readiness checklist consistency (roadmap Phase 6 consolidation).

Pins the ``## M7 readiness checklist`` section of ``BASELINE.md`` to the engine /
roadmap so the consolidated "are we at M7?" statement cannot silently drift:

- it enumerates the Phase 0 floor plus Phases 1-5 (the prior-phase signals M7
  consolidates), and
- every row names a real committed evidence source (a tracked file, never a
  narrative claim).

A dropped phase or a row that points at a non-existent source fails the test
instead of leaving a green-but-wrong checklist.
"""

from __future__ import annotations

import re
import sys
import unittest

from tests.qb_monorepo import REPO_ROOT, SHARED_DIR

BASELINE = REPO_ROOT / "BASELINE.md"
SECTION_HEADING = "## M7 readiness checklist"

# The roadmap phase set the checklist must enumerate: the Phase 0 floor plus
# Phases 1-5 (the prior-phase acceptance signals the M7 consolidation ties together).
EXPECTED_PHASES = {0, 1, 2, 3, 4, 5}

# A checklist table row whose first cell starts with "N —" / "N -" (a phase row).
_ROW = re.compile(r"^\|\s*(\d+)\s*[—-]")


def _checklist_section() -> str:
    text = BASELINE.read_text(encoding="utf-8")
    start = text.index(SECTION_HEADING)
    rest = text[start + len(SECTION_HEADING):]
    end = rest.find("\n## ")  # stop at the next top-level section
    return rest if end < 0 else rest[:end]


def _phase_rows() -> list[str]:
    return [line for line in _checklist_section().splitlines() if _ROW.match(line)]


class M7ReadinessChecklistTests(unittest.TestCase):
    def setUp(self) -> None:
        if not BASELINE.exists():
            self.skipTest("BASELINE.md missing")
        self.section = _checklist_section()
        self.rows = _phase_rows()

    def test_checklist_enumerates_every_roadmap_phase(self) -> None:
        phases = {int(_ROW.match(row).group(1)) for row in self.rows}
        self.assertEqual(
            phases, EXPECTED_PHASES,
            "the M7 readiness checklist must enumerate the Phase 0 floor plus Phases 1-5",
        )

    def test_every_row_names_a_real_committed_evidence_source(self) -> None:
        # Each row must cite at least one backticked path that EXISTS in the repo,
        # so a row can never read green by pointing at a non-existent or narrative
        # source rather than a committed gate.
        self.assertTrue(self.rows, "no phase rows found in the M7 readiness checklist")
        for row in self.rows:
            with self.subTest(row=row[:48]):
                paths = re.findall(r"`([^`]+)`", row)
                existing = [p for p in paths if (REPO_ROOT / p).exists()]
                self.assertTrue(
                    existing,
                    f"checklist row names no existing committed evidence file: {row[:80]}",
                )


    def test_release_gating_row_references_production_gate_conjuncts(self) -> None:
        # Pin the release-gating (operations) signal to the REAL conjunct set,
        # imported by name: a renamed or dropped production-gate conjunct fails here
        # instead of leaving a green-but-wrong checklist.
        scripts_dir = str(SHARED_DIR / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import production_gate  # noqa: E402  (path set above)

        self.assertTrue(production_gate.PRODUCTION_GATE_CHECKS)
        for conjunct in production_gate.PRODUCTION_GATE_CHECKS:
            self.assertIn(
                conjunct, self.section,
                f"the M7 readiness checklist omits production-gate conjunct {conjunct!r}",
            )

    def test_no_row_cites_a_qb_planning_file(self) -> None:
        # Grounding floor: readiness must rest on committed gates, never a `.qb/`
        # planning note (main-planning.md / sub-plans) -- the chat-memory failure
        # mode the project exists to eliminate. A captured-evidence path under
        # `.qb/audit/` is the only permitted `.qb/` reference.
        for row in self.rows:
            with self.subTest(row=row[:48]):
                for ref in re.findall(r"`([^`]+)`", row):
                    if ".qb/" in ref:
                        self.assertTrue(
                            ref.startswith(".qb/audit/"),
                            f"checklist row cites a .qb/ planning file as evidence: {ref}",
                        )


if __name__ == "__main__":
    unittest.main()
