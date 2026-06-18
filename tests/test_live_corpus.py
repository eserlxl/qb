"""Phase 3.1 -- the labelled corpus fixture builder.

Pins that tests/qb_corpus.build_corpus deterministically materializes at least
three labelled, git-initialized target repos with no host-state dependence
(re-running yields identical labels), and that every repo is trust-tagged with a
stdlib-only no-op verification command.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests import qb_corpus
from tests.qb_monorepo import REPO_ROOT, SHARED_DIR


def _load_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_driver():
    return _load_path("qb_live_validate_under_test", REPO_ROOT / "scripts" / "live_validate.py")


def _load_telemetry():
    return _load_path("qb_telemetry_under_test", SHARED_DIR / "scripts" / "telemetry.py")


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

    def test_invalid_trusted_code_preconditions_fail_closed(self) -> None:
        base = Path("unused")
        invalid = [
            qb_corpus.CorpusRepo(
                name="bad-trust", path=base, trust="untrusted",
                precondition=qb_corpus.NEUTRAL_PRECONDITION,
                verify_command=list(qb_corpus.NEUTRAL_VERIFY), labels={},
            ),
            qb_corpus.CorpusRepo(
                name="missing-precondition", path=base, trust="neutralized-noop",
                precondition="", verify_command=list(qb_corpus.NEUTRAL_VERIFY), labels={},
            ),
            qb_corpus.CorpusRepo(
                name="self-executing-neutralized", path=base, trust="neutralized-noop",
                precondition=qb_corpus.NEUTRAL_PRECONDITION,
                verify_command=["make", "test"], labels={},
            ),
        ]
        for repo in invalid:
            with self.subTest(repo=repo.name):
                with self.assertRaises(ValueError):
                    qb_corpus.validate_trusted_precondition(repo)

    def test_qb_headless_runs_over_corpus_and_telemetry_reads_back(self) -> None:
        lv = _load_driver()
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            repos = qb_corpus.build_corpus(base / "corpus")
            results = lv.run_over_corpus(repos, base / "out")
            self.assertEqual(len(results), len(repos))
            by_name = {r.repo: r for r in results}
            for repo in repos:
                res = by_name[repo.name]
                # A valid audit outcome (0 clean / 1 findings), never an internal error.
                self.assertIn(res.exit_code, (0, 1), f"{repo.name} exited {res.exit_code}")
                # Telemetry reads back without error (empty dict when A0 wrote none).
                self.assertIsInstance(res.telemetry, dict)
                # Every repo carrying seeded findings reports findings (exit 1).
                if repo.total_seeded() > 0:
                    self.assertTrue(res.findings_present, f"{repo.name} should report findings")
                    self.assertEqual(res.exit_code, 1)

    def test_corpus_ground_truth_precision_records_known_gap(self) -> None:
        # Compute precision from the corpus ground-truth labels and compare to the
        # telemetry precision metric. They measure DIFFERENT things: the labelled
        # corpus measures DETECTION ground truth, while telemetry.precision_estimate
        # is FIX keep-precision (kept/(kept+reverted)), which has no data under A0
        # report-only. We record that divergence as a labelled known gap rather than
        # passing it off as a match -- real fix precision needs the Phase 3.3 A2
        # campaign.
        t = _load_telemetry()
        fix_precision_empty = t.precision_estimate(0, 0)
        self.assertIsNone(fix_precision_empty)  # no fixes attempted at A0
        with tempfile.TemporaryDirectory() as d:
            repos = qb_corpus.build_corpus(Path(d))
            known_gaps = []
            for repo in repos:
                seeded = repo.total_seeded()
                # The corpus is fully labelled, so detection precision over its seeded
                # findings is 1.0 by construction (each seeded sink is a true positive).
                detection_precision = 1.0 if seeded else None
                if detection_precision != fix_precision_empty:
                    known_gaps.append(
                        f"{repo.name}: detection_precision={detection_precision} != "
                        f"fix precision_estimate(0,0)={fix_precision_empty} -- "
                        "detection ground truth vs A0 fix precision (synthetic corpus)")
            # The divergence is recorded as a labelled known gap, not a silent pass.
            self.assertTrue(known_gaps, "expected a labelled known-gap record")
            self.assertTrue(
                all("detection ground truth vs A0 fix precision" in gap for gap in known_gaps))

    def test_seeded_content_is_committed_in_each_repo(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            for repo in qb_corpus.build_corpus(Path(d)):
                status = subprocess.run(
                    ["git", "-C", str(repo.path), "status", "--porcelain"],
                    capture_output=True, text=True)
                self.assertEqual(status.stdout.strip(), "", f"{repo.name} has an uncommitted tree")


if __name__ == "__main__":
    unittest.main()
