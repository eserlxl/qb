"""Phase 1.3 -- pin the trusted-code precondition disclosure (direction B).

The trusted-code precondition is the load-bearing governance statement of boundary
direction B: A2/A3 autonomy is safe only against trusted code until full execution
sandboxing lands. It must stay disclosed consistently across every governance doc and
must never be silently relaxed. ``tests/test_doc_consistency.py`` pins it only in the
README + SECURITY.md; this module consolidates the invariant across ALL five
governance docs (so a drop in RUNBOOK/BASELINE/execution-sandbox is caught) and pins
the fail-closed certification default that backs it.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

from tests.qb_monorepo import REPO_ROOT, SHARED_DIR

POLICY_PATH = SHARED_DIR / "scripts/policy.py"

# Every governance doc that discloses the boundary; each must carry the precondition.
GOVERNANCE_DOCS = (
    REPO_ROOT / "SECURITY.md",
    REPO_ROOT / "README.md",
    REPO_ROOT / "BASELINE.md",
    REPO_ROOT / "RUNBOOK.md",
    REPO_ROOT / "docs/execution-sandbox.md",
)


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class TrustedCodePreconditionTests(unittest.TestCase):
    def test_precondition_disclosed_in_every_governance_doc(self) -> None:
        # The two load-bearing concepts -- "trusted code" and the "full execution
        # sandbox(ing)" boundary -- must be present in every governance doc, so the
        # precondition cannot be silently dropped from one while the others keep it.
        for doc in GOVERNANCE_DOCS:
            text = doc.read_text(encoding="utf-8").lower()
            self.assertIn(
                "trusted code", text,
                f"{doc.name} must disclose the trusted-code precondition",
            )
            self.assertIn(
                "full execution sandbox", text,
                f"{doc.name} must name the full-execution-sandbox boundary",
            )

    def test_security_md_carries_canonical_disclosure(self) -> None:
        text = (REPO_ROOT / "SECURITY.md").read_text(encoding="utf-8").lower()
        self.assertIn("trusted-code precondition", text,
                      "SECURITY.md must keep the canonical Trusted-code precondition heading")
        self.assertIn("not yet shipped", text,
                      "SECURITY.md must keep the full-execution-sandbox not-yet-shipped disclosure")

    def test_certification_default_is_fail_closed(self) -> None:
        # The disclosure is backed by a fail-closed signal: nothing certifies a full
        # execution sandbox today, so the precondition is never silently relaxable.
        policy = _load("qb_policy_precondition_under_test", POLICY_PATH)
        self.assertFalse(
            policy.full_execution_sandbox_certified(),
            "full execution sandbox must default to NOT certified (fail-closed)",
        )


if __name__ == "__main__":
    unittest.main()
