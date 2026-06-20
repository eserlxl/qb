"""Phase 1.1 -- pin the chosen sandbox-boundary direction (direction B).

Boundary direction B (govern-and-disclose) was selected in Phase 1.1: QB does not
ship a full execution sandbox; instead the trusted-code precondition stays loudly
disclosed and the autonomy ceiling stays fail-closed. These are load-bearing
invariants -- not doc sentences -- so this module pins them as tests so the
precondition cannot be silently relaxed nor the ceiling silently opened:

* the trusted-code precondition is present in SECURITY.md, and
* ``policy.sandbox_autonomy_ceiling`` caps autonomy below apply-verified (A2/A3)
  when full execution sandboxing is not available/certified, and only reaches A3
  when it is.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

from tests.qb_monorepo import REPO_ROOT, SHARED_DIR

POLICY_PATH = SHARED_DIR / "scripts/policy.py"
SECURITY_DOC = REPO_ROOT / "SECURITY.md"


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class SandboxBoundaryDirectionBTests(unittest.TestCase):
    def setUp(self) -> None:
        if not POLICY_PATH.exists():
            self.skipTest("policy module missing")
        self.policy = _load("qb_policy_boundary_under_test", POLICY_PATH)

    def test_trusted_code_precondition_is_disclosed_in_security(self) -> None:
        text = SECURITY_DOC.read_text(encoding="utf-8").lower()
        self.assertIn(
            "trusted-code precondition", text,
            "SECURITY.md must keep the trusted-code precondition heading",
        )
        self.assertIn(
            "trusted code", text,
            "SECURITY.md must state A2/A3 are safe only against trusted code",
        )
        self.assertIn(
            "not yet shipped", text,
            "SECURITY.md must keep the full-execution-sandbox not-yet-shipped disclosure",
        )

    def test_autonomy_ceiling_is_fail_closed_without_sandbox(self) -> None:
        # Direction B: when full execution sandboxing is not available/certified the
        # ceiling must cap BELOW apply-verified -- no A2/A3 working-tree apply.
        p = self.policy
        ceiling = p.sandbox_autonomy_ceiling(sandbox_available=False)
        self.assertEqual(ceiling, p.A1, "ceiling must be A1 when the sandbox is unavailable")
        self.assertLess(
            p._LEVELS.index(ceiling), p._LEVELS.index(p.A2),
            "fail-closed ceiling must rank below apply-verified (A2)",
        )

    def test_autonomy_ceiling_reaches_a3_only_with_sandbox(self) -> None:
        p = self.policy
        self.assertEqual(p.sandbox_autonomy_ceiling(sandbox_available=True), p.A3)


if __name__ == "__main__":
    unittest.main()
