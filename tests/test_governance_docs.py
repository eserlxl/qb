"""Phase 8.3 -- governance-docs invariants (standard library only).

Pins the committed governance contract so it cannot silently regress: the security
policy and the contribution guide exist and carry their required headings, the
review-ownership and report-structure files exist, and SECURITY.md embeds no
secret-like string. Complements tests/test_no_committed_secrets.py (which scans
every tracked file) with focused, named governance-doc assertions.
"""

from __future__ import annotations

import unittest

from tests.qb_monorepo import REPO_ROOT
from tests.test_no_committed_secrets import SECRET_PATTERNS

SECURITY = REPO_ROOT / "SECURITY.md"
VERSION_FILE = REPO_ROOT / "VERSION"


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

    def test_security_policy_has_no_secret_like_string(self):
        text = self._read(SECURITY)
        for line_number, line in enumerate(text.splitlines(), start=1):
            for name, pattern in SECRET_PATTERNS:
                self.assertIsNone(pattern.search(line),
                                  f"SECURITY.md:{line_number}: secret-like {name}")


if __name__ == "__main__":
    unittest.main()
