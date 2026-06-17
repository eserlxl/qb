"""Phase 3.1 -- the labelled corpus fixture builder.

Pins that tests/qb_corpus.build_corpus deterministically materializes at least
three labelled, git-initialized target repos with no host-state dependence
(re-running yields identical labels), and that every repo is trust-tagged with a
stdlib-only no-op verification command.
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tests import qb_corpus


@unittest.skipIf(subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
                 "git unavailable")
class LiveCorpusTests(unittest.TestCase):
    def test_builder_materializes_at_least_three_labelled_repos(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repos = qb_corpus.build_corpus(Path(d))
            self.assertGreaterEqual(len(repos), 3)
            for repo in repos:
                self.assertTrue((repo.path / ".git").is_dir(), f"{repo.name} is not a git repo")
                self.assertIn(repo.trust, ("trusted-verification", "neutralized-noop"))
                self.assertIsInstance(repo.labels, dict)
                # Verification command is a stdlib-only no-op (trusted to execute).
                self.assertEqual(repo.verify_command, ["python3", "-c", ""])
            # The corpus carries seeded findings (not all repos are clean).
            self.assertTrue(any(repo.total_seeded() > 0 for repo in repos))

    def test_builder_is_deterministic(self) -> None:
        def fingerprint(base):
            return [(r.name, r.trust, tuple(sorted(r.labels.items()))) for r in base]

        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            first = qb_corpus.build_corpus(Path(d1))
            second = qb_corpus.build_corpus(Path(d2))
            self.assertEqual(fingerprint(first), fingerprint(second))

    def test_seeded_content_is_committed_in_each_repo(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            for repo in qb_corpus.build_corpus(Path(d)):
                status = subprocess.run(
                    ["git", "-C", str(repo.path), "status", "--porcelain"],
                    capture_output=True, text=True)
                self.assertEqual(status.stdout.strip(), "", f"{repo.name} has an uncommitted tree")


if __name__ == "__main__":
    unittest.main()
