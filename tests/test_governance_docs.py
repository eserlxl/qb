"""Phase 8.3 -- governance-docs invariants (standard library only).

Pins the committed governance contract so it cannot silently regress: the security
policy and the contribution guide exist and carry their required headings, the
review-ownership and report-structure files exist, and SECURITY.md embeds no
secret-like string. Complements tests/test_no_committed_secrets.py (which scans
every tracked file) with focused, named governance-doc assertions.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest

from tests.qb_monorepo import REPO_ROOT
from tests.test_no_committed_secrets import SECRET_PATTERNS

SECURITY = REPO_ROOT / "SECURITY.md"
CONTRIBUTING = REPO_ROOT / "CONTRIBUTING.md"
RUNBOOK = REPO_ROOT / "RUNBOOK.md"
CODEOWNERS = REPO_ROOT / "CODEOWNERS"
ISSUE_TEMPLATE = REPO_ROOT / ".github/ISSUE_TEMPLATE/bug_report.md"
PR_TEMPLATE = REPO_ROOT / ".github/PULL_REQUEST_TEMPLATE.md"
VERSION_FILE = REPO_ROOT / "VERSION"
ACCEPTED_FINDINGS = REPO_ROOT / "docs" / "accepted-findings.md"
ACCEPTED_LOADER = REPO_ROOT / "shared" / "scripts" / "accepted_findings.py"


def _load_module(name, path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class GovernanceDocsTest(unittest.TestCase):
    def _read(self, path):
        self.assertTrue(path.is_file(), f"missing governance doc: {path}")
        return path.read_text(encoding="utf-8")

    def test_security_policy_present_with_required_headings(self):
        text = self._read(SECURITY)
        for heading in ("## Reporting a Vulnerability", "## Supported Versions"):
            self.assertIn(heading, text, f"SECURITY.md missing heading: {heading}")
        self.assertIn("github.com/eserlxl/qb/issues", text,
                      "SECURITY.md must name a public reporting channel")
        self.assertIn("VERSION", text, "SECURITY.md must tie supported versions to VERSION")
        self.assertIn("trusted code", text.lower(),
                      "SECURITY.md must state the trusted-code precondition for A2/A3")

    def test_public_security_reporting_boundary_is_explicit(self):
        text = self._read(SECURITY).lower()
        self.assertIn("public", text)
        self.assertIn("do **not** paste", text)
        self.assertIn("secret values", text)
        self.assertIn("sensitive exploit payloads", text)
        self.assertIn("redact", text)
        self.assertIn("synthetic examples", text)
        self.assertIn("trusted code", text)

    def test_required_governance_docs_exist(self):
        # The governance contract fails if ANY required doc/file is missing.
        for path in (SECURITY, CONTRIBUTING, RUNBOOK, CODEOWNERS, ISSUE_TEMPLATE,
                     PR_TEMPLATE, ACCEPTED_FINDINGS, ACCEPTED_LOADER):
            self.assertTrue(path.is_file(), f"missing required governance doc: {path}")
        accepted_text = self._read(ACCEPTED_FINDINGS)
        for phrase in ("reviewer", "rationale", "fail-closed", "self_audit_clean"):
            self.assertIn(phrase, accepted_text)
        loader = _load_module("qb_accepted_findings_governance", ACCEPTED_LOADER)
        sample = (
            "## Accepted\n"
            "- `QBF-GOOD` -- reviewed false positive (reviewer: maintainer)\n"
            "- `QBF-NO-REVIEWER` -- missing reviewer marker\n"
            "- `QBF-NO-RATIONALE` (reviewer: maintainer)\n"
            "    - `QBF-INDENTED` -- example only (reviewer: maintainer)\n"
            "## Other\n"
            "- `QBF-OTHER` -- wrong section (reviewer: maintainer)\n"
        )
        self.assertEqual(loader.parse_accepted_ids(sample), {"QBF-GOOD"})
        runbook = self._read(RUNBOOK)
        for phrase in (".qb/audit/findings.jsonl", "docs/accepted-findings.md",
                       "self_audit_clean", "production-gate.json",
                       "release-authorization.json"):
            self.assertIn(phrase, runbook)

    def test_contributing_has_required_headings(self):
        text = self._read(CONTRIBUTING)
        for heading in ("## Versioning and changelog", "## Contribution workflow",
                        "## No secrets"):
            self.assertIn(heading, text, f"CONTRIBUTING.md missing heading: {heading}")

    def test_contributing_present_with_required_sections(self):
        text = self._read(CONTRIBUTING)
        self.assertIn("make sync", text)
        self.assertIn("make check", text)
        self.assertIn("shared/", text)               # shared/ sync requirement
        self.assertIn("bump-version.sh", text)        # versioning/changelog convention
        self.assertIn("gate of record", text.lower())  # gate-of-record reference
        self.assertIn("secret", text.lower())          # no-secrets rule

    def test_review_ownership_and_templates_present(self):
        # Review ownership + report structure are explicit (Phase 8.3).
        codeowners = self._read(CODEOWNERS)
        self.assertRegex(codeowners, r"(?m)^\*\s+@\S+",
                         "CODEOWNERS must assign a default owner (e.g. '* @owner')")
        self.assertTrue(ISSUE_TEMPLATE.is_file(), f"missing issue template: {ISSUE_TEMPLATE}")
        pr = self._read(PR_TEMPLATE)
        self.assertIn("make check", pr, "PR template must reference the gate of record")

    def test_issue_template_warns_against_public_sensitive_details(self):
        text = self._read(ISSUE_TEMPLATE).lower()
        self.assertIn("public issue", text)
        self.assertIn("do not include secrets", text)
        self.assertIn("sensitive exploit payloads", text)
        self.assertIn("step-by-step exploit details", text)
        self.assertIn("redact", text)
        self.assertIn("synthetic examples", text)

    def test_security_policy_has_no_secret_like_string(self):
        text = self._read(SECURITY)
        for line_number, line in enumerate(text.splitlines(), start=1):
            for name, pattern in SECRET_PATTERNS:
                self.assertIsNone(pattern.search(line),
                                  f"SECURITY.md:{line_number}: secret-like {name}")


if __name__ == "__main__":
    unittest.main()
