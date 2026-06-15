"""Phase 6.1 -- every shared engine artifact is mapped and fanned out byte-equal.

The Phases 1-5 engine modules live under shared/scripts/ and were wired into the
scripts/sync.sh MAP incrementally. This test pins the completeness contract for the
engine specifically: every shared/scripts/*.py is referenced as a sync source and
exists byte-identical in all three platform destinations, so no engine artifact can
silently bypass the single-source-of-truth contract.
"""

from __future__ import annotations

import filecmp
import unittest
from pathlib import Path

from tests.qb_monorepo import PLATFORMS_DIR, REPO_ROOT, SHARED_DIR

SYNC_SH = REPO_ROOT / "scripts/sync.sh"
SHARED_SCRIPTS = SHARED_DIR / "scripts"

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


if __name__ == "__main__":
    unittest.main()
