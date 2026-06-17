"""Confidence-band policy for built-in producer analyzers."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

SCRIPTS_DIR = SHARED_DIR / "scripts"


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class AnalyzerConfidencePolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ai = _load("qb_analyzer_interface", SCRIPTS_DIR / "analyzer_interface.py")
        self.core = _load("qb_analyzer_core", SCRIPTS_DIR / "analyzer_core.py")
        self.quality = _load("qb_analyzer_quality_confidence", SCRIPTS_DIR / "analyzer_quality.py")
        self.dependency = _load("qb_analyzer_dependency_confidence", SCRIPTS_DIR / "analyzer_dependency.py")
        self.license = _load("qb_analyzer_license_confidence", SCRIPTS_DIR / "analyzer_license.py")
        self.config = _load("qb_analyzer_config_confidence", SCRIPTS_DIR / "analyzer_config.py")
        self.breadth = _load("qb_analyzer_breadth_confidence", SCRIPTS_DIR / "analyzer_breadth.py")
        self.cfg = self.ai.AnalyzerConfig()

    def test_policy_declares_current_producer_rule_bands(self) -> None:
        expected = {
            ("secret-hygiene", "secret-pattern"): "high",
            ("quality-correctness", "tool-diagnostic"): "medium",
            ("dependency-audit", "manifest-hygiene"): "medium",
            ("dependency-audit", "network-advisory"): "high",
            ("license-hygiene", "missing-license"): "high",
            ("license-hygiene", "empty-license"): "medium",
            ("config-hygiene", "committed-config"): "medium",
            ("workflow-actions", "broad-action-ref"): "medium",
        }
        for key, band in expected.items():
            with self.subTest(key=key):
                self.assertEqual(self.core.confidence_for_rule(*key), band)
        with self.assertRaises(KeyError):
            self.core.confidence_for_rule("dependency-audit", "new-unreviewed-rule")

    def test_secret_findings_use_high_confidence_policy(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write(root, "settings.txt", "token = 'sk-AAAAAAAAAAAAAAAAAAAAAAAA'\n")
            findings = self.core.SecretHygieneAnalyzer().analyze(str(root), self.cfg)
        self.assertTrue(findings)
        self.assertEqual({f.confidence for f in findings}, {"high"})

    def test_quality_tool_diagnostics_use_medium_confidence_policy(self) -> None:
        adapter = self.quality.ToolAdapter(
            name="stub-tool",
            executable="python3",
            category="quality",
            build_argv=lambda root: ["python3", "-c", "pass"],
            parse=lambda stdout, stderr: [
                {"path": "mod.py", "line": 3, "severity": "warn", "rule": "Q001", "message": "issue"}
            ],
            severity_map={"warn": "P2"},
            default_severity="P3",
        )
        with tempfile.TemporaryDirectory() as d:
            findings = self.quality.QualityAnalyzer([adapter]).analyze(d, self.cfg)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].confidence, "medium")

    def test_dependency_findings_use_manifest_and_advisory_policy(self) -> None:
        def source(name, spec):
            return [{"id": "CVE-2026-0001", "severity": "high"}] if name == "flask" else []

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write(root, "requirements.txt", "flask\n")
            analyzer = self.dependency.DependencyAnalyzer(advisory_source=source)
            findings = analyzer.analyze(str(root), self.ai.AnalyzerConfig(allow_networked=True))

        offline = [f for f in findings if "Offline manifest audit" in f.rationale]
        networked = [f for f in findings if "Network-enriched" in f.rationale]
        self.assertEqual({f.confidence for f in offline}, {"medium"})
        self.assertEqual({f.confidence for f in networked}, {"high"})

    def test_license_findings_use_missing_and_empty_policy(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            missing = self.license.LicenseAnalyzer().analyze(d, self.cfg)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write(root, "LICENSE", "stub\n")
            empty = self.license.LicenseAnalyzer().analyze(str(root), self.cfg)
        self.assertEqual(missing[0].confidence, "high")
        self.assertEqual(empty[0].confidence, "medium")

    def test_config_and_workflow_heuristics_use_medium_confidence_policy(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write(root, ".env", "API_KEY=example\n")
            config_findings = self.config.ConfigHygieneAnalyzer().analyze(str(root), self.cfg)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write(root, ".github/workflows/ci.yml", "steps:\n  - uses: actions/checkout@v4\n")
            workflow_findings = self.breadth.WorkflowActionAnalyzer().analyze(str(root), self.cfg)

        self.assertEqual({f.confidence for f in config_findings}, {"medium"})
        self.assertEqual({f.confidence for f in workflow_findings}, {"medium"})


if __name__ == "__main__":
    unittest.main()
