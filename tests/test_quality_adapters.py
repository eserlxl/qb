"""Phase 2.3 -- offline quality/correctness adapters.

Pins: present-tool normalization (severity mapping + provenance + conformant
findings), graceful skip when a tool is absent (zero-setup core intact), the
capability report (ran vs skipped), argv-only invocation, and read-only behavior.
Hermetic: the present-tool path uses ``python3`` (always available) as a stand-in
tool; the absent path uses a deliberately nonexistent executable.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

MODULE_PATH = SHARED_DIR / "scripts/analyzer_quality.py"

PRESENT_PATH_COVERAGE_AUDIT = {
    "stubbed_tool": "python3 stand-in exercises detect -> argv-run -> normalize -> Finding without real pyflakes",
    "asserted": (
        "schema-conformant finding",
        "category is currently the generic quality stub",
        "severity maps native warn to P2",
        "provenance names the stub tool",
        "capability report records the tool as ran",
    ),
    "gap": "does not yet assert the built-in pyflakes adapter emits category correctness",
}

ABSENT_PATH_COVERAGE_AUDIT = {
    "simulated_absence": "deliberately nonexistent executable drives ToolAdapter.available through shutil.which == None",
    "asserted": (
        "analyze returns no findings",
        "capability report has no ran adapters",
        "capability report records adapter name",
        "capability report records reason tool-unavailable",
    ),
    "gap": "no-raise is currently implicit in the test flow rather than named as an assertion",
}


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _stub_adapter(qa, name="stub-tool", executable="python3", severity_map=None, diag_severity="warn"):
    # Backed by python3 (always present); output is ignored and a canned diagnostic
    # is returned, exercising the real detect->argv-run->normalize->Finding path.
    return qa.ToolAdapter(
        name=name,
        executable=executable,
        category="quality",
        build_argv=lambda root: ["python3", "-c", "pass"],
        parse=lambda stdout, stderr: [
            {"path": "mod.py", "line": 3, "severity": diag_severity, "rule": "Q001", "message": "example issue"}
        ],
        severity_map=severity_map if severity_map is not None else {"warn": "P2"},
        default_severity="P3",
    )


class QualityAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        if not MODULE_PATH.exists():
            self.skipTest(f"analyzer_quality missing: {MODULE_PATH}")
        self.qa = _load("qb_analyzer_quality_under_test", MODULE_PATH)
        self.validate = sys.modules["qb_analyzer_interface"].validate_finding

    def test_present_tool_emits_normalized_conformant_findings(self) -> None:
        analyzer = self.qa.QualityAnalyzer([_stub_adapter(self.qa)])
        with tempfile.TemporaryDirectory() as d:
            findings = analyzer.analyze(d, None)
        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertEqual(self.validate(f), [])
        self.assertEqual(f.category, "quality")
        self.assertEqual(f.severity, "P2")          # mapped from native "warn"
        self.assertIn("Reported by stub-tool", f.rationale)  # provenance
        self.assertEqual(f.evidence, "mod.py:3")
        self.assertEqual(analyzer.last_capability_report["ran"], ["stub-tool"])

    def test_unknown_native_severity_falls_back_to_default(self) -> None:
        analyzer = self.qa.QualityAnalyzer([_stub_adapter(self.qa, diag_severity="mystery")])
        with tempfile.TemporaryDirectory() as d:
            findings = analyzer.analyze(d, None)
        self.assertEqual(findings[0].severity, "P3")  # default_severity

    def test_absent_tool_is_skipped_gracefully(self) -> None:
        analyzer = self.qa.QualityAnalyzer([
            _stub_adapter(self.qa, name="missing-tool", executable="qb-nonexistent-tool-xyz")
        ])
        with tempfile.TemporaryDirectory() as d:
            findings = analyzer.analyze(d, None)
        self.assertEqual(findings, [])
        self.assertEqual(analyzer.last_capability_report["ran"], [])
        skipped = analyzer.last_capability_report["skipped"]
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0]["adapter"], "missing-tool")
        self.assertEqual(skipped[0]["reason"], "tool-unavailable")

    def test_mixed_present_and_absent(self) -> None:
        analyzer = self.qa.QualityAnalyzer([
            _stub_adapter(self.qa, name="present"),
            _stub_adapter(self.qa, name="absent", executable="qb-nonexistent-tool-xyz"),
        ])
        with tempfile.TemporaryDirectory() as d:
            findings = analyzer.analyze(d, None)
        self.assertEqual(len(findings), 1)
        self.assertEqual(analyzer.last_capability_report["ran"], ["present"])
        self.assertEqual([s["adapter"] for s in analyzer.last_capability_report["skipped"]], ["absent"])

    def test_conforms_to_interface_and_is_offline(self) -> None:
        analyzer = self.qa.QualityAnalyzer([_stub_adapter(self.qa)])
        self.assertIsInstance(analyzer, sys.modules["qb_analyzer_interface"].Analyzer)
        self.assertTrue(analyzer.descriptor.offline)
        self.assertEqual(analyzer.descriptor.categories, ("quality", "correctness"))

    def test_default_adapters_use_argv_lists(self) -> None:
        for adapter in self.qa.default_quality_adapters():
            self.assertIsInstance(adapter.build_argv("/some/root"), list)

    def test_analyzer_is_read_only(self) -> None:
        analyzer = self.qa.QualityAnalyzer([_stub_adapter(self.qa)])
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "keep.txt").write_text("x", encoding="utf-8")
            before = {p.name: p.stat().st_mtime_ns for p in Path(d).iterdir()}
            analyzer.analyze(d, None)
            after = {p.name: p.stat().st_mtime_ns for p in Path(d).iterdir()}
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
