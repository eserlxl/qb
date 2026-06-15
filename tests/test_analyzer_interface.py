"""Conformance test for the pluggable read-only analyzer interface (Phase 1.2).

The analyzer interface is canonical host-neutral IP under
``shared/scripts/analyzer_interface.py``. It fixes the contract every QB analyzer
implements: a read-only ``analyze(repo_root, config) -> list[Finding]`` method, a
capability descriptor (stable id, covered categories, offline/networked flag),
and a deterministic registry. A single trivial reference analyzer proves the
wiring without embedding real detection logic.

This test pins: protocol conformance, Phase-1.1 finding conformance of emitted
findings, deterministic identity, deterministic registry enumeration, the
graceful-absence rule, the offline/networked enable filter, and the read-only
obligation (the working tree is unchanged after a reference run).
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

MODULE_PATH = SHARED_DIR / "scripts/analyzer_interface.py"


def _load():
    spec = importlib.util.spec_from_file_location("qb_analyzer_interface_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _stub(mod, an_id, *, offline=True, categories=("quality",)):
    class _Stub:
        descriptor = mod.AnalyzerDescriptor(id=an_id, categories=categories, offline=offline)

        def analyze(self, repo_root, config):
            return []

    return _Stub()


class AnalyzerInterfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        if not MODULE_PATH.exists():
            self.skipTest(f"analyzer interface module missing: {MODULE_PATH}")
        self.mod = _load()

    # --- protocol + descriptor --------------------------------------------
    def test_reference_analyzer_satisfies_protocol(self) -> None:
        self.assertIsInstance(self.mod.ReferenceAnalyzer(), self.mod.Analyzer)

    def test_reference_descriptor_is_offline_and_valid(self) -> None:
        d = self.mod.ReferenceAnalyzer().descriptor
        self.assertTrue(d.offline, "reference analyzer must be offline")
        self.assertEqual(d.validate(), [])
        self.assertTrue(set(d.categories).issubset(self.mod.CATEGORIES))
        self.assertTrue(d.id.strip())

    def test_descriptor_rejects_unknown_category(self) -> None:
        d = self.mod.AnalyzerDescriptor(id="x", categories=("not-a-category",), offline=True)
        self.assertTrue(any("categories" in e for e in d.validate()), d.validate())

    # --- output binds to the frozen Finding schema ------------------------
    def test_reference_analyzer_emits_conformant_findings(self) -> None:
        findings = self.mod.ReferenceAnalyzer().analyze(str(SHARED_DIR.parent), self.mod.AnalyzerConfig())
        self.assertEqual(len(findings), 1, "reference analyzer emits exactly one finding")
        for f in findings:
            self.assertEqual(self.mod.validate_finding(f), [], f"non-conformant finding: {f}")

    def test_reference_finding_is_deterministic(self) -> None:
        ref = self.mod.ReferenceAnalyzer()
        cfg = self.mod.AnalyzerConfig()
        first = ref.analyze(".", cfg)[0]
        second = ref.analyze(".", cfg)[0]
        self.assertEqual(first.id, second.id, "reference finding id must be stable across runs")

    # --- registry ---------------------------------------------------------
    def test_registry_enumerates_in_deterministic_id_order(self) -> None:
        reg = self.mod.AnalyzerRegistry()
        reg.register(_stub(self.mod, "b-analyzer"))
        reg.register(_stub(self.mod, "a-analyzer"))
        self.assertEqual([a.descriptor.id for a in reg.analyzers()], ["a-analyzer", "b-analyzer"])

    def test_registry_rejects_duplicate_id(self) -> None:
        reg = self.mod.AnalyzerRegistry()
        reg.register(_stub(self.mod, "dup"))
        with self.assertRaises(ValueError):
            reg.register(_stub(self.mod, "dup"))

    def test_registry_graceful_absence(self) -> None:
        reg = self.mod.AnalyzerRegistry()

        def _broken_loader():
            raise RuntimeError("optional analyzer unavailable")

        result = reg.register_optional(_broken_loader, "networked-cve")
        self.assertIsNone(result)
        self.assertEqual([a.descriptor.id for a in reg.analyzers()], [])
        self.assertEqual(len(reg.skipped), 1)
        skipped_id, reason = reg.skipped[0]
        self.assertEqual(skipped_id, "networked-cve")
        self.assertIn("unavailable", reason)

    def test_enabled_filters_networked_when_not_allowed(self) -> None:
        reg = self.mod.AnalyzerRegistry()
        reg.register(_stub(self.mod, "offline-an", offline=True))
        reg.register(_stub(self.mod, "net-an", offline=False))
        offline_only = [a.descriptor.id for a in reg.enabled(allow_networked=False)]
        self.assertEqual(offline_only, ["offline-an"])
        both = [a.descriptor.id for a in reg.enabled(allow_networked=True)]
        self.assertEqual(both, ["net-an", "offline-an"])

    def test_default_registry_contains_reference_analyzer(self) -> None:
        ids = [a.descriptor.id for a in self.mod.default_registry().analyzers()]
        self.assertIn(self.mod.ReferenceAnalyzer().descriptor.id, ids)

    # --- read-only obligation ---------------------------------------------
    def test_reference_analyzer_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "keep.txt").write_text("x", encoding="utf-8")
            before = {p.name: p.stat().st_mtime_ns for p in Path(d).iterdir()}
            self.mod.ReferenceAnalyzer().analyze(d, self.mod.AnalyzerConfig())
            after = {p.name: p.stat().st_mtime_ns for p in Path(d).iterdir()}
            self.assertEqual(before, after, "analyzer must not write to the inspected tree")


if __name__ == "__main__":
    unittest.main()
