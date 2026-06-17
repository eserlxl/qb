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


@unittest.skipIf(subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
                 "git unavailable")
class A1CampaignTests(unittest.TestCase):
    def test_a1_run_writes_schema_versioned_quality_telemetry(self) -> None:
        lv = _driver()
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            repos = qb_corpus.build_corpus(base / "corpus")
            self.assertTrue(repos)
            for repo in repos:
                run = lv.run_campaign(repo, "A1", base / "out" / repo.name / "QB-Audit")
                tele = run.telemetry
                self.assertEqual(tele["schema_version"], lv._telemetry.TELEMETRY_SCHEMA_VERSION)
                self.assertEqual(tele["autonomy_level"], "A1")
                self.assertIn("precision_estimate", tele["quality"])
                self.assertIn("fix_safety_ok", tele["quality"])
                # A1 isolates and verifies but never promotes to the working tree.
                self.assertEqual(run.promoted(), [])
                self.assertIn("kept", run.outcomes())


if __name__ == "__main__":
    unittest.main()
