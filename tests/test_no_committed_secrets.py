"""Repo-wide guard: no real credential is committed to any tracked file.

Each platform's validate.sh scans only its own subtree, and the shared validator
scans only the generated .qb/ tree, so a secret committed anywhere else
in the monorepo would slip through CI. This test enumerates every git-tracked
file and fails if any line matches a known secret class. Deliberate test
fixtures opt out with a trailing ``pragma: allowlist secret`` marker.
"""

from __future__ import annotations

import re
import subprocess
import unittest

from tests.qb_monorepo import REPO_ROOT

ALLOW_MARKER = "pragma: allowlist secret"

BLOCKED_SUFFIXES = (".pyc", ".zip", ".png", ".jpg", ".jpeg", ".gif", ".svg")

# The canonical secret classes (mirrors the shared validator's analyzer_core coverage).
SECRET_PATTERNS = [
    ("openai_api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("github_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("github_legacy_pat", re.compile(r"\bghp_[A-Za-z0-9]{20,}\b")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA|AGPA|AIDA|ANPA|AROA|AIPA|ANVA)[0-9A-Z]{16}\b")),
    ("private_key", re.compile(r"BEGIN (?:[A-Z0-9]+ )?PRIVATE KEY")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("stripe_secret_key", re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{20,}\b")),
]


def _tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.splitlines()


class NoCommittedSecretsTest(unittest.TestCase):
    def test_no_secret_patterns_in_tracked_files(self) -> None:
        findings: list[str] = []
        for rel in _tracked_files():
            if rel.endswith(BLOCKED_SUFFIXES):
                continue
            try:
                text = (REPO_ROOT / rel).read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for line_number, line in enumerate(text.splitlines(), start=1):
                if ALLOW_MARKER in line:
                    continue
                for name, pattern in SECRET_PATTERNS:
                    if pattern.search(line):
                        findings.append(f"{rel}:{line_number}: {name}")
        self.assertEqual(
            findings,
            [],
            "committed secret-like strings found (add an inline "
            f"'{ALLOW_MARKER}' marker if a fixture is intentional):\n"
            + "\n".join(findings),
        )

    def test_patterns_detect_aws_sts_and_stripe(self) -> None:
        # Positive coverage: the broadened set catches AWS STS (ASIA) and Stripe keys,
        # not just long-term AKIA. Tokens are built by concatenation so this source
        # carries no literal credential to trip the scan above.
        by_name = dict(SECRET_PATTERNS)
        self.assertTrue(by_name["aws_access_key"].search("ASIA" + "A" * 16))
        self.assertTrue(by_name["aws_access_key"].search("AKIA" + "B" * 16))
        self.assertTrue(by_name["stripe_secret_key"].search("sk_live_" + "a" * 24))
        self.assertTrue(by_name["stripe_secret_key"].search("sk_test_" + "b" * 24))


if __name__ == "__main__":
    unittest.main()
