"""Phase 3.2 -- the A1 corpus campaign.

Runs declared-A1 sessions over the labelled corpus (each fix verified by the
repo's stdlib-only no-op) and pins: a redacted, schema-versioned telemetry record
per run carrying the precision/fix-safety quality fields; working-tree
byte-identity after each A1 run (isolation only); the cold-start clamp (declared
A2/A3 with no telemetry resolves to A1 and promotes nothing); and that each
persisted record is loadable as the A2-eligible input Phase 3.3 consumes.
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


def _driver():
    return _load_path("qb_live_validate_a1", REPO_ROOT / "scripts" / "live_validate.py")


def _git_porcelain(repo: Path) -> str:
    return subprocess.run(["git", "-C", str(repo), "status", "--porcelain"],
                          capture_output=True, text=True).stdout.strip()


EXPECTED_CORPUS_LABELS = {
    "injection_pair": {"injection": 2},
    "traversal": {"path-traversal": 1},
    "mixed": {"injection": 2, "path-traversal": 1},
    "clean": {},
}


@unittest.skipIf(subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
                 "git unavailable")
class A1CampaignTests(unittest.TestCase):
    def test_campaign_corpus_label_map_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repos = qb_corpus.build_corpus(Path(d))
        self.assertEqual({repo.name: repo.labels for repo in repos}, EXPECTED_CORPUS_LABELS)
        self.assertTrue(any(labels for labels in EXPECTED_CORPUS_LABELS.values()))

    def test_a1_run_writes_schema_versioned_quality_telemetry(self) -> None:
        lv = _driver()
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            repos = qb_corpus.build_corpus(base / "corpus")
            self.assertTrue(repos)
            for repo in repos:
                run = lv.run_campaign(repo, "A1", base / "out" / repo.name / ".qb/audit")
                tele = run.telemetry
                self.assertEqual(tele["schema_version"], lv._telemetry.TELEMETRY_SCHEMA_VERSION)
                self.assertEqual(tele["autonomy_level"], "A1")
                self.assertIn("precision_estimate", tele["quality"])
                self.assertIn("fix_safety_ok", tele["quality"])
                # A1 isolates and verifies but never promotes to the working tree.
                self.assertEqual(run.promoted(), [])
                self.assertIn("kept", run.outcomes())

    def test_working_tree_byte_identical_after_a1(self) -> None:
        lv = _driver()
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            for repo in qb_corpus.build_corpus(base / "corpus"):
                self.assertEqual(_git_porcelain(repo.path), "", f"{repo.name} dirty before run")
                lv.run_campaign(repo, "A1", base / "out" / repo.name / ".qb/audit")
                # A1 confines writes to throwaway isolation: the target tree is unchanged.
                self.assertEqual(_git_porcelain(repo.path), "",
                                 f"{repo.name} working tree changed after A1 run")

    def test_cold_start_declared_a2_a3_clamps_to_a1(self) -> None:
        lv = _driver()
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            for repo in qb_corpus.build_corpus(base / "corpus"):
                for level in ("A2", "A3"):
                    run = lv.run_campaign(
                        repo, level, base / "out" / repo.name / level / ".qb/audit",
                        prior_telemetry=None)
                    for result in run.results:
                        self.assertEqual(result["earned_ceiling"], "A1", f"{repo.name} {level}")
                    self.assertEqual(run.promoted(), [], f"{repo.name} {level} promoted on cold start")

    def test_a1_telemetry_is_loadable_and_a2_eligible(self) -> None:
        lv = _driver()
        rs = _load_path("qb_run_store_a1c", SHARED_DIR / "scripts" / "run_store.py")
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            for repo in qb_corpus.build_corpus(base / "corpus"):
                run = lv.run_campaign(repo, "A1", base / "out" / repo.name / ".qb/audit")
                loaded = rs.load_prior_telemetry(run.output_dir)
                self.assertEqual(loaded["schema_version"], lv._telemetry.TELEMETRY_SCHEMA_VERSION)
                # The A1 run kept a green-verified fix, so the record earns A2 for Phase 3.3.
                self.assertEqual(lv._telemetry.max_permitted_autonomy(loaded), "A2")


if __name__ == "__main__":
    unittest.main()
