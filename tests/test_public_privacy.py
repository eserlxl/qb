"""Repo-wide guard: no private / machine-local identifier in a public doc.

QB's release-facing docs ship publicly, so a leaked machine-local path
(``/home/<user>/...``, ``/Users/<user>/...``, ``/private/tmp/...``, a Windows
user path) or a stray UUID in one of them is a real privacy exposure that the
credential guard (``test_no_committed_secrets``) does not catch -- it covers
*credentials* only. This test scans the canonical release-facing doc set and
fails if any private identifier is present.

It imports ``PRIVATE_PATTERNS`` / ``scan_text`` / ``public_docs`` from the single
source (``scripts/public_privacy.py``) rather than re-declaring the patterns, so a
new pattern in the scanner is enforced here automatically -- the same single-source
discipline ``test_no_committed_secrets`` uses for ``SECRET_PATTERNS``. Standard
library only. Leak fixtures are built by concatenation so this source carries no
literal private path.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest

from tests.qb_monorepo import REPO_ROOT


def _load_public_privacy():
    """Import the scanner module from scripts/ (its single source of truth)."""
    path = REPO_ROOT / "scripts" / "public_privacy.py"
    spec = importlib.util.spec_from_file_location("qb_public_privacy", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_pp = _load_public_privacy()
PRIVATE_PATTERNS = _pp.PRIVATE_PATTERNS
scan_text = _pp.scan_text
public_docs = _pp.public_docs
ALLOW_MARKER = _pp.ALLOW_MARKER


class PublicPrivacyGuardTest(unittest.TestCase):
    def test_no_private_identifiers_in_public_docs(self) -> None:
        docs = public_docs(REPO_ROOT)
        self.assertTrue(docs, "no release-facing public docs were found to scan")
        findings: list[str] = []
        for path in docs:
            rel = path.relative_to(REPO_ROOT)
            text = path.read_text(encoding="utf-8")
            for line_number, name in scan_text(text):
                findings.append(f"{rel}:{line_number}: {name}")
        self.assertEqual(
            findings,
            [],
            "private identifier(s) found in a release-facing public doc (add an "
            f"inline '{ALLOW_MARKER}' marker if an example is intentional):\n"
            + "\n".join(findings),
        )

    def test_patterns_detect_unix_and_macos_paths(self) -> None:
        # Built by concatenation so this source carries no literal private path.
        by_name = dict(PRIVATE_PATTERNS)
        self.assertTrue(by_name["unix_home_path"].search("/home/" + "alice/work"))
        self.assertTrue(by_name["macos_users_path"].search("/Users/" + "bob/dev"))
        self.assertTrue(by_name["macos_private_path"].search("/private/" + "tmp/x"))
        self.assertTrue(by_name["macos_private_path"].search("/private/" + "var/y"))

    def test_patterns_detect_windows_and_uuid(self) -> None:
        by_name = dict(PRIVATE_PATTERNS)
        self.assertTrue(by_name["windows_user_path"].search("C:" + "\\Users\\" + "carol"))
        uuid = "12345678-" + "1234-1234-1234-" + "123456789abc"
        self.assertTrue(by_name["uuid"].search("id=" + uuid))

    def test_allowlist_marker_suppresses_a_finding(self) -> None:
        leak = "see /home/" + "dave/notes for details"
        self.assertTrue(scan_text(leak), "control: an unmarked leak must be flagged")
        marked = leak + "  # " + ALLOW_MARKER
        self.assertEqual(
            scan_text(marked), [], "a line with the allowlist marker must be skipped"
        )

    def test_clean_text_has_no_findings(self) -> None:
        clean = "Run `make check`; the gate of record lives in RUNBOOK.md.\n~/.config is fine."
        self.assertEqual(scan_text(clean), [])


if __name__ == "__main__":
    unittest.main()
