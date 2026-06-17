"""Phase 8.1 -- gate-of-record invariant (standard library only).

Pins the chosen quality gate so it cannot silently drift: the CI workflow and the
opt-in pre-push hook both invoke `make check`, the workflow declares a
least-privilege permissions block, and the gate-of-record policy doc names the gate.
Uses only the standard library plus the repo-root helper.
"""

from __future__ import annotations

import unittest

from tests.qb_monorepo import REPO_ROOT

WORKFLOW = REPO_ROOT / ".github/workflows/validate.yml"
PRE_PUSH_HOOK = REPO_ROOT / "scripts/hooks/pre-push"
RUNBOOK = REPO_ROOT / "RUNBOOK.md"


class CiGateTest(unittest.TestCase):
    def _read(self, path):
        self.assertTrue(path.is_file(), f"missing gate surface: {path}")
        return path.read_text(encoding="utf-8")

    def test_workflow_invokes_make_check(self):
        # The chosen CI gate mechanism must invoke `make check`.
        self.assertIn("make check", self._read(WORKFLOW),
                      "validate.yml must invoke 'make check' as the gate")

    def test_workflow_declares_least_privilege_permissions(self):
        # An explicit least-privilege permissions block (contents: read), never write.
        text = self._read(WORKFLOW)
        self.assertIn("permissions:", text, "validate.yml must declare a permissions block")
        self.assertIn("contents: read", text,
                      "validate.yml permissions must be least-privilege (contents: read)")
        self.assertNotIn("contents: write", text,
                         "validate.yml must not grant contents: write")

    def test_pre_push_hook_runs_make_check(self):
        # The opt-in local gate (the alternate enforcement path) also runs make check.
        text = self._read(PRE_PUSH_HOOK)
        self.assertIn("make", text)
        self.assertIn("check", text)

    def test_gate_of_record_doc_names_the_gate(self):
        # The policy doc (RUNBOOK 'Gate of record') must exist and name `make check`.
        runbook = self._read(RUNBOOK)
        self.assertIn("## Gate of record", runbook,
                      "RUNBOOK must carry the 'Gate of record' policy section")
        section = runbook.split("## Gate of record", 1)[1]
        self.assertIn("make check", section,
                      "the Gate of record section must name 'make check'")


if __name__ == "__main__":
    unittest.main()
