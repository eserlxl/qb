"""Repo-wide guard: no real credential is committed to any tracked file.

Each platform's validate.sh scans only its own subtree, and the shared validator
scans only the generated .qb/ tree, so a secret committed anywhere else
in the monorepo would slip through CI. This test enumerates every git-tracked
file and fails if any line matches a known secret class. Deliberate test
fixtures opt out with a trailing ``pragma: allowlist secret`` marker.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest

from tests.qb_monorepo import REPO_ROOT, SHARED_DIR

ALLOW_MARKER = "pragma: allowlist secret"

BLOCKED_SUFFIXES = (".pyc", ".zip", ".png", ".jpg", ".jpeg", ".gif", ".svg")


def _load_engine_secret_patterns():
    """Import SECRET_PATTERNS from analyzer_core, the engine's single source.

    A hand-maintained copy here silently drifts from the engine (it had already
    fallen behind the azure_storage_key class); importing the canonical list keeps
    this repo-wide guard enforcing exactly what the analyzer detects, so a new
    engine pattern is covered everywhere without editing this file.
    """
    path = SHARED_DIR / "scripts" / "analyzer_core.py"
    spec = importlib.util.spec_from_file_location("qb_analyzer_core", path)
    module = importlib.util.module_from_spec(spec)
    # Register before exec: the module's own @dataclass definitions resolve their
    # __module__ namespace via sys.modules under deferred annotations.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.SECRET_PATTERNS


# The canonical secret classes, from analyzer_core (the single source of truth).
SECRET_PATTERNS = _load_engine_secret_patterns()


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

    def test_patterns_detect_github_app_and_google_keys(self) -> None:
        # Positive coverage for the GitHub OAuth/app/refresh prefixes and Google API
        # keys. Tokens are built by concatenation so this source carries no literal
        # credential to trip the repo-wide scan above.
        by_name = dict(SECRET_PATTERNS)
        for prefix in ("gho_", "ghu_", "ghs_", "ghr_"):
            self.assertTrue(
                by_name["github_app_token"].search(prefix + "A" * 36),
                f"{prefix} GitHub token not detected",
            )
        # ghp_ (classic PAT) stays the legacy class, not github_app_token.
        self.assertIsNone(by_name["github_app_token"].search("ghp_" + "A" * 36))
        self.assertTrue(by_name["github_legacy_pat"].search("ghp_" + "A" * 36))
        self.assertTrue(by_name["google_api_key"].search("AIza" + "b" * 35))


if __name__ == "__main__":
    unittest.main()
