"""Phase 6.1 -- every shared engine artifact is mapped and fanned out byte-equal.

The Phases 1-5 engine modules live under shared/scripts/ and were wired into the
scripts/sync.sh MAP incrementally. This test pins the completeness contract for the
engine specifically: every shared/scripts/*.py is referenced as a sync source and
exists byte-identical in all three platform destinations, so no engine artifact can
silently bypass the single-source-of-truth contract.
"""

from __future__ import annotations

import filecmp
import importlib.util
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

from tests.qb_monorepo import PLATFORMS_DIR, REPO_ROOT, SHARED_DIR

SYNC_SH = REPO_ROOT / "scripts/sync.sh"
SHARED_SCRIPTS = SHARED_DIR / "scripts"


def _load_mod(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

# Engine modules delivered by the audit/hardening pivot (Phases 1-5 + 6.3).
EXPECTED_ENGINE_MODULES = {
    "finding_schema.py", "analyzer_interface.py", "analyzer_core.py", "audit_runner.py",
    "command_safety.py", "analyzer_quality.py", "analyzer_dependency.py", "fixer.py",
    "isolation.py", "verification_gate.py", "policy.py", "orchestrator.py", "budget.py",
    "review.py", "run_store.py", "report.py", "qb_headless.py",
}


def _platform_destinations(module: str):
    return [
        PLATFORMS_DIR / "claude-code/scripts" / module,
        PLATFORMS_DIR / "cursor/scripts" / module,
        PLATFORMS_DIR / "codex/plugins/qb/skills/qb/scripts" / module,
    ]


class EngineArtifactTests(unittest.TestCase):
    def setUp(self) -> None:
        if not SHARED_SCRIPTS.is_dir() or not SYNC_SH.is_file():
            self.skipTest("shared scripts or sync.sh missing")
        self.sync_text = SYNC_SH.read_text(encoding="utf-8")
        self.shared_py = {p.name for p in SHARED_SCRIPTS.glob("*.py")}

    def test_expected_engine_modules_present_in_shared(self) -> None:
        missing = EXPECTED_ENGINE_MODULES - self.shared_py
        self.assertEqual(missing, set(), f"engine modules missing from shared/scripts: {missing}")

    def test_every_shared_script_is_mapped(self) -> None:
        for name in sorted(self.shared_py):
            with self.subTest(module=name):
                self.assertIn(f"scripts/{name}|", self.sync_text,
                              f"shared/scripts/{name} is not wired into the sync MAP")

    def test_engine_modules_fan_out_byte_equal(self) -> None:
        if not all((PLATFORMS_DIR / d).is_dir() for d in ("claude-code", "cursor", "codex")):
            self.skipTest("not all platforms built")
        for name in sorted(self.shared_py):
            source = SHARED_SCRIPTS / name
            for dest in _platform_destinations(name):
                with self.subTest(module=name, dest=dest):
                    self.assertTrue(dest.is_file(), f"missing platform copy: {dest}")
                    self.assertTrue(filecmp.cmp(source, dest, shallow=False),
                                    f"platform copy drifted from shared source: {dest}")


@unittest.skipIf(subprocess.run(["git", "--version"], capture_output=True).returncode != 0, "git unavailable")
class EvidenceConfinementTests(unittest.TestCase):
    """A fix-attempt evidence record reports the established confinement controls."""

    def test_fix_attempt_evidence_reports_established_confinement_controls(self) -> None:
        gate = _load_mod("qb_vg_artifacts", SHARED_SCRIPTS / "verification_gate.py")
        iso = _load_mod("qb_iso_artifacts", SHARED_SCRIPTS / "isolation.py")
        cs = _load_mod("qb_cs_artifacts", SHARED_SCRIPTS / "command_safety.py")
        verify = ["python3", "-c",
                  "import pathlib,sys; sys.exit(0 if pathlib.Path('flag.txt').read_text().strip()=='GOOD' else 1)"]
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            for key, value in (("user.email", "t@example.com"), ("user.name", "QB Test"),
                               ("commit.gpgsign", "false")):
                subprocess.run(["git", "-C", str(repo), "config", key, value], check=True)
            (repo / "flag.txt").write_text("BAD\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "init"], check=True)
            isolation = iso.Isolation(repo, level=iso.A1, run_id="evidence").open()
            try:
                plan = types.SimpleNamespace(
                    finding=types.SimpleNamespace(id="QBF-evidence0000"), verify_command=verify)
                record = gate.gate_fix(isolation, plan,
                                       apply_fn=lambda i: i.write_file("flag.txt", "GOOD\n"))
                evidence = record.to_dict()
                self.assertIn("confinement_controls", evidence)
                self.assertIsInstance(evidence["confinement_controls"], list)
                # Control names only -- never command output.
                if "process_group" in cs.available_confinement_controls():
                    self.assertEqual(record.outcome, "kept")
                    self.assertIn("process_group", evidence["confinement_controls"])
            finally:
                isolation.teardown()


if __name__ == "__main__":
    unittest.main()
