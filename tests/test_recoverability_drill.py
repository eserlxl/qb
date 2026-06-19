"""Phase 7.1 -- whole-run recoverability drill.

A clean drill cycle (capture -> mutate -> whole-run rollback -> baseline_clean)
returns a structured pass record, fully reverts the mutation, and releases the
namespaced reversal ref -- reusing release_gate's rollback path.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR


def _load(name: str, filename: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SHARED_DIR / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


drill = _load("qb_recoverability_drill", "recoverability_drill.py")


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def _init_repo(repo: Path) -> None:
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "QB Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "a.txt").write_text("baseline\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "baseline")


@unittest.skipIf(subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
                 "git unavailable")
class RecoverabilityDrillTest(unittest.TestCase):
    def test_clean_pass_cycle(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            _init_repo(repo)
            output_dir = Path(d) / ".qb/audit"
            record = drill.run_and_persist(str(repo), "drill-run-1", output_dir)

            self.assertEqual(set(record), {
                "schema_version",
                "run_id",
                "baseline_ref",
                "baseline_sha_len",
                "baseline_clean",
                "mutation_error",
                "passed",
            })
            self.assertEqual(
                record["schema_version"],
                drill.RECOVERABILITY_EVIDENCE_SCHEMA_VERSION,
            )
            self.assertTrue(record["passed"])
            self.assertTrue(record["baseline_clean"])
            self.assertEqual(record["run_id"], "drill-run-1")
            self.assertTrue(record["baseline_ref"].startswith("refs/qb-baseline/drill-run-1"))
            baseline_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
            self.assertEqual(record["baseline_sha_len"], len(baseline_sha))
            self.assertNotIn(baseline_sha, json.dumps(record, sort_keys=True))
            self.assertIsNone(record["mutation_error"])
            # the default scratch mutation was rolled back; tree clean at baseline
            self.assertFalse((repo / ".qb-recoverability-drill.scratch").exists())
            self.assertEqual(_git(repo, "status", "--porcelain").stdout.strip(), "")
            # the namespaced reversal ref was released
            refs = _git(repo, "for-each-ref", "--format=%(refname)").stdout
            self.assertNotIn(record["baseline_ref"], refs)
            evidence_path = output_dir / drill.RECOVERABILITY_EVIDENCE_FILENAME
            self.assertEqual(drill.read_evidence(output_dir), record)
            self.assertTrue(
                evidence_path.read_text(encoding="utf-8")
                .splitlines()[1]
                .startswith("  \"baseline_clean\"")
            )

            secret = "ghp_" + "A" * 30
            secret_dir = Path(d) / "secret-evidence"
            drill.persist_evidence({**record, "run_id": secret}, secret_dir)
            raw = (secret_dir / drill.RECOVERABILITY_EVIDENCE_FILENAME).read_text(
                encoding="utf-8"
            )
            self.assertNotIn(secret, raw)
            self.assertIn("<redacted>", raw)

    def test_custom_mutation_is_fully_reverted(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            _init_repo(repo)

            def mutate(root):
                (Path(root) / "new.txt").write_text("x\n", encoding="utf-8")
                (Path(root) / "a.txt").write_text("changed\n", encoding="utf-8")

            record = drill.run_drill(str(repo), "drill-run-2", mutate_fn=mutate)
            self.assertTrue(record["passed"])
            self.assertFalse((repo / "new.txt").exists())
            self.assertEqual((repo / "a.txt").read_text(encoding="utf-8"), "baseline\n")

    def test_mutation_exception_is_failed_but_rolled_back(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            _init_repo(repo)

            def mutate(root):
                (Path(root) / "new.txt").write_text("x\n", encoding="utf-8")
                (Path(root) / "a.txt").write_text("changed\n", encoding="utf-8")
                raise RuntimeError("fixture failure")

            record = drill.run_drill(str(repo), "drill-raises", mutate_fn=mutate)
            self.assertFalse(record["passed"])
            self.assertTrue(record["baseline_clean"])
            self.assertEqual(record["mutation_error"], "RuntimeError")
            self.assertFalse((repo / "new.txt").exists())
            self.assertEqual((repo / "a.txt").read_text(encoding="utf-8"), "baseline\n")
            self.assertEqual(_git(repo, "status", "--porcelain").stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
