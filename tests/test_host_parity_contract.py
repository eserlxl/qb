"""Phase 5.2/5.3 -- machine-checkable per-host capability parity.

Pins the invariants the committed contract (platforms/PARITY.md) asserts, against
the filesystem and scripts/sync.sh rather than hardcoded duplicates:

  1. each engine-bearing host (claude-code, cursor, codex) ships the engine modules;
  2. Antigravity ships NO engine module anywhere under its tree (planning-only);
  3. Antigravity is NOT a scripts/sync.sh MAP destination;
  4. the PARITY.md contract matches that on-disk reality.

A fail-closed self-check guards the predicate itself: the "is engine-bearing"
predicate must distinguish an engine-bearing host from a planning-only one, so an
always-true predicate cannot make invariant (2) pass vacuously.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.qb_monorepo import REPO_ROOT

# Representative core of the audit/harden engine. These are unambiguously engine
# (not planner/validator) modules and are synced into every engine-bearing host.
ENGINE_MODULES = ("audit_runner.py", "orchestrator.py", "budget.py", "release_gate.py")

ENGINE_HOST_SCRIPT_DIRS = {
    "claude-code": REPO_ROOT / "platforms/claude-code/scripts",
    "cursor": REPO_ROOT / "platforms/cursor/scripts",
    "codex": REPO_ROOT / "platforms/codex/plugins/qb/skills/qb/scripts",
}
ANTIGRAVITY_ROOT = REPO_ROOT / "platforms/antigravity"
SYNC_SH = REPO_ROOT / "scripts/sync.sh"
PARITY_DOC = REPO_ROOT / "platforms/PARITY.md"
EXPECTED_PARITY_MATRIX = {
    "Claude Code": {
        "Planning workflow": "yes",
        "Audit/harden engine": "yes",
    },
    "Cursor": {
        "Planning workflow": "yes",
        "Audit/harden engine": "yes",
    },
    "Codex": {
        "Planning workflow": "yes",
        "Audit/harden engine": "yes",
    },
    "Antigravity": {
        "Planning workflow": "yes",
        "Audit/harden engine": "no (planning-only)",
    },
}


def _has_engine(script_dir: Path) -> bool:
    """The contract's predicate: a directory is engine-bearing iff it holds every
    engine module."""
    return all((script_dir / module).is_file() for module in ENGINE_MODULES)


def _parity_matrix() -> dict[str, dict[str, str]]:
    lines = PARITY_DOC.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "## Capability matrix":
            table_lines = []
            for row in lines[i + 1:]:
                if row.strip().startswith("## "):
                    break  # stop at the next section so other tables are not parsed
                if row.strip().startswith("|"):
                    table_lines.append(row.strip())
            break
    else:
        raise AssertionError("PARITY.md omits the Capability matrix section")

    rows = [
        [cell.strip() for cell in row.strip("|").split("|")]
        for row in table_lines
        if not set(row.replace("|", "").strip()) <= {"-", ":"}
    ]
    if not rows:
        raise AssertionError("PARITY.md capability matrix has no rows")

    header = rows[0]
    if header != ["Host", "Planning workflow", "Audit/harden engine"]:
        raise AssertionError(f"unexpected PARITY.md matrix header: {header}")

    return {
        row[0]: dict(zip(header[1:], row[1:]))
        for row in rows[1:]
    }


class HostParityContractTest(unittest.TestCase):
    def test_engine_present_in_engine_bearing_hosts(self):
        for host, script_dir in ENGINE_HOST_SCRIPT_DIRS.items():
            self.assertTrue(script_dir.is_dir(), f"{host}: missing engine dir {script_dir}")
            missing = [m for m in ENGINE_MODULES if not (script_dir / m).is_file()]
            self.assertEqual(missing, [], f"{host} engine dir omits engine modules: {missing}")

    def test_engine_absent_under_antigravity(self):
        self.assertTrue(ANTIGRAVITY_ROOT.is_dir(), "antigravity package missing")
        engine_names = set(ENGINE_MODULES)
        intruders = sorted(
            str(p.relative_to(REPO_ROOT))
            for p in ANTIGRAVITY_ROOT.rglob("*.py")
            if p.name in engine_names
        )
        self.assertEqual(intruders, [],
                         f"Antigravity is planning-only but ships engine modules: {intruders}")

    def test_antigravity_is_not_a_sync_destination(self):
        self.assertTrue(SYNC_SH.is_file(), "scripts/sync.sh missing")
        offenders = [
            line.strip()
            for line in SYNC_SH.read_text(encoding="utf-8").splitlines()
            # MAP entries are "source|destination" pairs; a destination under the
            # antigravity tree would make it a sync surface.
            if "|platforms/antigravity/" in line
        ]
        self.assertEqual(offenders, [],
                         f"Antigravity must not be a sync.sh destination: {offenders}")

    def test_contract_doc_matches_reality(self):
        self.assertTrue(PARITY_DOC.is_file(), "platforms/PARITY.md missing")
        matrix = _parity_matrix()
        # The doc's engine-bearing claim must hold on disk.
        self.assertEqual(matrix["Claude Code"]["Audit/harden engine"], "yes")
        self.assertEqual(matrix["Cursor"]["Audit/harden engine"], "yes")
        self.assertEqual(matrix["Codex"]["Audit/harden engine"], "yes")
        self.assertTrue(all(_has_engine(d) for d in ENGINE_HOST_SCRIPT_DIRS.values()))
        self.assertEqual(
            matrix["Antigravity"]["Audit/harden engine"],
            "no (planning-only)",
        )
        self.assertFalse(_has_engine(ANTIGRAVITY_ROOT / "skills/qb/scripts"))

        # The engine-module roster the _has_engine predicate checks must match the
        # modules PARITY.md names, so a rename in either place fails here rather than
        # silently desyncing the predicate from the contract.
        doc_text = PARITY_DOC.read_text(encoding="utf-8")
        named = re.search(r"contains the engine modules \(([^)]*)\)", doc_text, re.DOTALL)
        self.assertIsNotNone(named, "PARITY.md does not enumerate the engine modules")
        named_modules = set(re.findall(r"`([A-Za-z0-9_]+\.py)`", named.group(1)))
        self.assertEqual(
            named_modules, set(ENGINE_MODULES),
            f"PARITY.md engine modules {sorted(named_modules)} != predicate roster "
            f"{sorted(ENGINE_MODULES)}",
        )

    def test_capability_matrix_pins_host_decision_points(self):
        matrix = _parity_matrix()
        self.assertEqual(matrix, EXPECTED_PARITY_MATRIX)
        self.assertTrue(
            all(row["Planning workflow"] == "yes" for row in matrix.values()),
            "all four hosts must ship the planning workflow",
        )
        engine_hosts = sorted(
            host for host, row in matrix.items()
            if row["Audit/harden engine"] == "yes"
        )
        self.assertEqual(engine_hosts, ["Claude Code", "Codex", "Cursor"])
        planning_only_hosts = [
            host for host, row in matrix.items()
            if row["Audit/harden engine"] == "no (planning-only)"
        ]
        self.assertEqual(planning_only_hosts, ["Antigravity"])

    def test_parity_predicate_is_fail_closed(self):
        # The predicate must discriminate: True for an engine host, False for the
        # planning-only host. An always-true predicate would make the absence
        # invariant vacuous.
        self.assertTrue(_has_engine(ENGINE_HOST_SCRIPT_DIRS["claude-code"]))
        self.assertFalse(_has_engine(ANTIGRAVITY_ROOT / "skills/qb/scripts"))
        self.assertFalse(_has_engine(REPO_ROOT / "no/such/dir"))


if __name__ == "__main__":
    unittest.main()
