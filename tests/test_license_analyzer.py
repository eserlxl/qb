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
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            return self.mod.LicenseAnalyzer().analyze(str(root), self.cfg)

    def _manifest(self, files: dict) -> list:
        # Every manifest case here ships a real root LICENSE, so the root is
        # licensed and the only possible findings are manifest-undeclared ones.
        return self._analyze({"LICENSE": _MIT, **files})

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

    def test_dual_license_naming_is_recognized(self) -> None:
        # Conventional split-license names must not be reported as a missing license.
        self.assertEqual(self._analyze({"LICENSE-MIT": _MIT}), [])
        self.assertEqual(self._analyze({"LICENSE-APACHE": _MIT}), [])

    def test_unrelated_license_named_file_does_not_satisfy(self) -> None:
        # A source file that merely starts with "license" is not a license declaration,
        # so a repo whose only such file is license_manager.py is still flagged.
        findings = self._analyze({"license_manager.py": "def f():\n    return 1\n"})
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, "license")

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

    # --- manifest-undeclared-license (root is licensed) -----------------------

    def test_manifest_without_license_is_flagged_when_root_licensed(self) -> None:
        findings = self._manifest({"pkg/package.json": '{"name": "x", "version": "1.0.0"}'})
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, "license")
        self.assertEqual(findings[0].severity, "P3")
        self.assertEqual(findings[0].confidence, "medium")
        self.assertEqual(findings[0].fix_strategy, "manual")
        self.assertEqual(findings[0].evidence, "pkg/package.json:1")
        self.assertEqual(self.ai.validate_finding(findings[0]), [])

    def test_pyproject_and_cargo_without_license_are_flagged(self) -> None:
        findings = self._manifest({
            "py/pyproject.toml": '[project]\nname = "x"\nversion = "0.1"\n',
            "cr/Cargo.toml": '[package]\nname = "x"\nversion = "0.1.0"\n',
            "po/pyproject.toml": '[tool.poetry]\nname = "x"\nversion = "0.1"\n',
        })
        self.assertEqual(
            {f.evidence for f in findings},
            {"py/pyproject.toml:1", "cr/Cargo.toml:1", "po/pyproject.toml:1"},
        )

    def test_manifest_with_declared_license_is_clean(self) -> None:
        for files in (
            {"pkg/package.json": '{"name": "x", "license": "MIT"}'},
            {"pkg/package.json": '{"name": "x", "license": {"type": "MIT", "url": "u"}}'},
            {"pkg/package.json": '{"name": "x", "licenses": [{"type": "MIT"}]}'},
            {"py/pyproject.toml": '[project]\nname = "x"\nlicense = "MIT"\n'},
            {"py/pyproject.toml": '[project]\nname = "x"\nlicense = {file = "LICENSE"}\n'},
            {"py/pyproject.toml": '[project]\nname = "x"\nlicense-files = ["LICENSE"]\n'},
            {"py/pyproject.toml": '[project]\nname = "x"\ndynamic = ["license"]\n'},
            {"py/pyproject.toml": '[project]\nname = "x"\nclassifiers = ["License :: OSI Approved :: MIT License"]\n'},
            {"cr/Cargo.toml": '[package]\nname = "x"\nlicense = "MIT OR Apache-2.0"\n'},
            {"cr/Cargo.toml": '[package]\nname = "x"\nlicense.workspace = true\n'},
            {"cr/Cargo.toml": '[package]\nname = "x"\nlicense-file = "LICENSE"\n'},
        ):
            self.assertEqual(self._manifest(files), [], files)

    def test_non_package_manifests_are_not_flagged(self) -> None:
        # private / unpublished / identity-less / tool-only manifests declare no
        # distributable package, so an absent license must not fire.
        for files in (
            {"pkg/package.json": '{"name": "x", "private": true}'},
            {"pkg/package.json": '{"name": "my-monorepo", "version": "0.0.0", "workspaces": ["packages/*"]}'},
            {"pkg/package.json": '{"version": "1.0.0"}'},
            {"py/pyproject.toml": '[build-system]\nrequires = ["setuptools"]\n'},
            {"cr/Cargo.toml": '[package]\nname = "x"\npublish = false\n'},
            {"cr/Cargo.toml": '[package]\nname = "x"\npublish = []\n'},
            {"cr/Cargo.toml": '[workspace]\nmembers = ["a"]\n'},
        ):
            self.assertEqual(self._manifest(files), [], files)

    def test_bom_prefixed_manifest_is_still_flagged(self) -> None:
        # A UTF-8 BOM (common in Windows-emitted manifests, accepted by npm) must
        # not silently hide a license-omitting package: the BOM is stripped before
        # parsing so the omission is still detected.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "LICENSE").write_text(_MIT, encoding="utf-8")
            pkg = root / "pkg"
            pkg.mkdir()
            (pkg / "package.json").write_bytes(
                b'\xef\xbb\xbf{"name": "x", "version": "1.0.0"}')
            findings = self.mod.LicenseAnalyzer().analyze(str(root), self.cfg)
            self.assertEqual([f.evidence for f in findings], ["pkg/package.json:1"])

    def test_sample_path_manifests_are_excluded(self) -> None:
        for prefix in ("examples", "fixtures", "testdata", "demo"):
            self.assertEqual(
                self._manifest({f"{prefix}/pkg/package.json": '{"name": "x"}'}), [],
                f"{prefix}/ manifest should be excluded")

    def test_malformed_manifest_degrades_to_no_finding(self) -> None:
        self.assertEqual(self._manifest({"pkg/package.json": '{"name": broken'}), [])
        self.assertEqual(self._manifest({"py/pyproject.toml": 'name = "x" [oops\n'}), [])

    def test_manifest_scan_skipped_when_root_unlicensed(self) -> None:
        # No root license: only the root missing-license finding fires; package
        # manifests are NOT additionally flagged (the root rule already states it).
        findings = self._analyze({"pkg/package.json": '{"name": "x"}'})
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].evidence, "LICENSE:1")


if __name__ == "__main__":
    unittest.main()
