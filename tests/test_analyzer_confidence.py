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
        self.schema = _load("qb_finding_schema", SCRIPTS_DIR / "finding_schema.py")
        self.core = _load("qb_analyzer_core", SCRIPTS_DIR / "analyzer_core.py")
        self.runner = _load("qb_audit_runner_confidence", SCRIPTS_DIR / "audit_runner.py")
        self.quality = _load("qb_analyzer_quality_confidence", SCRIPTS_DIR / "analyzer_quality.py")
        self.dependency = _load("qb_analyzer_dependency_confidence", SCRIPTS_DIR / "analyzer_dependency.py")
        self.license = _load("qb_analyzer_license_confidence", SCRIPTS_DIR / "analyzer_license.py")
        self.config = _load("qb_analyzer_config_confidence", SCRIPTS_DIR / "analyzer_config.py")
        self.breadth = _load("qb_analyzer_breadth_confidence", SCRIPTS_DIR / "analyzer_breadth.py")
        self.cfg = self.ai.AnalyzerConfig()

    def test_confidence_policy_covers_default_registry(self) -> None:
        registered = sorted(
            analyzer.descriptor.id for analyzer in self.runner.build_default_registry().analyzers()
        )
        self.assertEqual(sorted(self.core.CONFIDENCE_POLICY), registered)
        for analyzer_id, rules in self.core.CONFIDENCE_POLICY.items():
            with self.subTest(analyzer=analyzer_id):
                self.assertTrue(rules, f"{analyzer_id} has no confidence rules")
                invalid = sorted(
                    band for band in rules.values() if band not in self.schema.CONFIDENCE_BANDS
                )
                self.assertEqual(invalid, [])

    def test_every_command_injection_rule_kind_is_banded(self) -> None:
        # Enumerate command-injection rule kinds from the analyzer's OWN source of
        # truth (command_safety._RULES, the table scan_text_for_command_risks
        # walks) -- not a hand-maintained duplicate -- and assert each carries a
        # CONFIDENCE_POLICY band, so a new pattern added to _RULES without a
        # reviewed band fails `make check` instead of only raising KeyError at
        # runtime. command-injection passes each rule_key straight to
        # confidence_for_rule, so the rule_key IS the policy rule kind here.
        emittable = {rule_key for rule_key, *_rest in self.runner._cs._RULES}
        self.assertTrue(emittable, "command_safety._RULES is empty")
        banded = set(self.core.CONFIDENCE_POLICY["command-injection"])
        self.assertEqual(
            sorted(emittable - banded), [],
            "command-injection rule kind(s) emittable from _RULES but unbanded",
        )
        for rule_key in sorted(emittable):
            with self.subTest(rule_key=rule_key):
                self.assertIn(
                    self.core.confidence_for_rule("command-injection", rule_key),
                    self.schema.CONFIDENCE_BANDS,
                )

    def test_policy_declares_current_producer_rule_bands(self) -> None:
        expected = {
            ("secret-hygiene", "secret-pattern"): "high",
            ("command-injection", "shell-string-subprocess"): "high",
            ("command-injection", "system-shell-call"): "high",
            ("command-injection", "system-pipe-call"): "medium",
            ("command-injection", "subprocess-getoutput"): "medium",
            ("command-injection", "node-shell-exec"): "high",
            ("command-injection", "dynamic-eval"): "medium",
            ("command-injection", "dynamic-exec"): "medium",
            ("command-injection", "path-traversal-sink"): "medium",
            ("quality-correctness", "tool-diagnostic"): "medium",
            ("dependency-audit", "manifest-hygiene"): "medium",
            ("dependency-audit", "network-advisory"): "high",
            ("license-hygiene", "missing-license"): "high",
            ("license-hygiene", "empty-license"): "medium",
            ("config-hygiene", "committed-config"): "medium",
            ("workflow-actions", "broad-action-ref"): "medium",
            ("workflow-actions", "broad-permissions"): "medium",
        }
        for key, band in expected.items():
            with self.subTest(key=key):
                self.assertEqual(self.core.confidence_for_rule(*key), band)
        with self.assertRaises(KeyError):
            self.core.confidence_for_rule("dependency-audit", "new-unreviewed-rule")

        text = "\n".join([
            "# qb-ignore: system-shell-call reviewed false positive",
            "os.system(cmd)",
            "# qb-ignore: dynamic-eval wrong rule",
            "os.system(cmd)",
            "# qb-ignore: system-shell-call",
            "os.system(cmd)",
            "os.system(cmd)  # qb-ignore: * inline accepted fixture",
            "",
        ])
        self.assertEqual(
            self.core.suppression_reason_for_line(text, 2, "system-shell-call"),
            "reviewed false positive",
        )
        self.assertIsNone(self.core.suppression_reason_for_line(text, 4, "system-shell-call"))
        self.assertIsNone(self.core.suppression_reason_for_line(text, 6, "system-shell-call"))
        self.assertEqual(
            self.core.suppression_reason_for_line(text, 7, "system-shell-call"),
            "inline accepted fixture",
        )

    def test_secret_findings_use_high_confidence_policy(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            token = "sk-" + ("A" * 24)
            _write(root, "settings.txt", f"token = '{token}'\n")
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
