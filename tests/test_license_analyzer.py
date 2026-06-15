"""Net-new license-hygiene analyzer.

Completes the previously wired-but-unproduced ``license`` finding category (it is
in the frozen schema and bound to the fixer's ``license-review`` recipe, but no
analyzer emitted it). Pins: missing-license and empty-license detection, a clean
no-finding case for a real license, schema conformance, read-only behavior, and
registration in the default audit registry.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

LICENSE_PATH = SHARED_DIR / "scripts/analyzer_license.py"
INTERFACE_PATH = SHARED_DIR / "scripts/analyzer_interface.py"
RUNNER_PATH = SHARED_DIR / "scripts/audit_runner.py"

_MIT = (
    "MIT License\n\nCopyright (c) 2026 Example\n\nPermission is hereby granted, "
    "free of charge, to any person obtaining a copy of this software.\n"
)


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class LicenseAnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        if not LICENSE_PATH.exists():
            self.skipTest("analyzer_license not built yet")
        self.mod = _load("qb_analyzer_license_under_test", LICENSE_PATH)
        # The analyzer loads the interface under the canonical name; share it so
        # the Finding class identity matches for validate_finding.
        self.ai = _load("qb_analyzer_interface", INTERFACE_PATH)
        self.cfg = self.ai.AnalyzerConfig()

    def _analyze(self, files: dict) -> list:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name, content in files.items():
                (root / name).write_text(content, encoding="utf-8")
            return self.mod.LicenseAnalyzer().analyze(str(root), self.cfg)

    def test_missing_license_is_flagged(self) -> None:
        findings = self._analyze({"README.md": "# project\n"})
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, "license")
        self.assertEqual(findings[0].severity, "P2")
        self.assertEqual(findings[0].fix_strategy, "manual")
        self.assertNotEqual(findings[0].evidence, ".:1")  # not the reference no-op sentinel
        self.assertEqual(self.ai.validate_finding(findings[0]), [])

    def test_empty_license_is_flagged(self) -> None:
        findings = self._analyze({"LICENSE": "   \n"})
        self.assertEqual(len(findings), 1)
        self.assertIn("empty", findings[0].rationale.lower())
        self.assertEqual(self.ai.validate_finding(findings[0]), [])

    def test_real_license_is_clean(self) -> None:
        self.assertEqual(self._analyze({"LICENSE": _MIT}), [])
        self.assertEqual(self._analyze({"COPYING.md": _MIT}), [])

    def test_descriptor_and_default_registration(self) -> None:
        descriptor = self.mod.LicenseAnalyzer().descriptor
        self.assertEqual(descriptor.id, "license-hygiene")
        self.assertEqual(descriptor.categories, ("license",))
        self.assertTrue(descriptor.offline)
        runner = _load("qb_audit_runner_license_test", RUNNER_PATH)
        ids = {a.descriptor.id for a in runner.build_default_registry().analyzers()}
        self.assertIn("license-hygiene", ids)

    def test_analyzer_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "README.md").write_text("x\n", encoding="utf-8")
            before = sorted(p.name for p in root.iterdir())
            self.mod.LicenseAnalyzer().analyze(str(root), self.cfg)
            self.assertEqual(before, sorted(p.name for p in root.iterdir()))


if __name__ == "__main__":
    unittest.main()
