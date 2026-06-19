"""Resilience of RunStore read-side methods against corrupt on-disk artifacts.

Resolves council S1: a single malformed/truncated line in findings.jsonl (e.g.
from a killed run) used to propagate an uncaught json.JSONDecodeError, while
read_telemetry already degraded to {}. These tests pin that every reader now
degrades to its empty value ([] / {}) on a corrupt file rather than raising.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

STORE_PATH = SHARED_DIR / "scripts/run_store.py"


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class RunStoreResilienceTests(unittest.TestCase):
    def setUp(self) -> None:
        if not STORE_PATH.exists():
            self.skipTest("run_store missing")
        self.rs = _load("qb_run_store_resilience", STORE_PATH)

    def _store(self, d):
        return self.rs.RunStore(Path(d) / self.rs.OUTPUT_DIR_NAME).open()

    def test_read_findings_tolerates_malformed_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            # one valid line followed by a truncated/malformed one
            (store.root / self.rs.FINDINGS_FILENAME).write_text(
                '{"id": "a", "category": "quality"}\n{"id": "b", "categ\n',
                encoding="utf-8",
            )
            self.assertEqual(store.read_findings(), [])  # degraded, not raised

    def test_read_summary_tolerates_corrupt_json(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            (store.root / self.rs.SUMMARY_FILENAME).write_text("{not json", encoding="utf-8")
            self.assertEqual(store.read_summary(), {})

    def test_read_self_audit_and_production_gate_tolerate_corrupt(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            (store.root / self.rs.SELF_AUDIT_FILENAME).write_text("}{", encoding="utf-8")
            (store.root / self.rs.PRODUCTION_GATE_FILENAME).write_text("nope", encoding="utf-8")
            self.assertEqual(store.read_self_audit(), {})
            self.assertEqual(store.read_production_gate(), {})

    def test_read_evidence_tolerates_corrupt_record(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            (store.evidence_dir / "bad.json").write_text("{truncated", encoding="utf-8")
            self.assertEqual(store.read_evidence(), [])


if __name__ == "__main__":
    unittest.main()
