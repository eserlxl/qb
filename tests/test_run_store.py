"""Phase 5.1 -- run-state & evidence store.

Pins: the fixed-name layout + identifier check; findings/evidence/log/summary
round-trip; mandatory secret redaction before write; the kept-fix-requires-handle
rule; append-only seq ordering; and the opt-in overwrite policy.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

STORE_PATH = SHARED_DIR / "scripts/run_store.py"
SCHEMA_PATH = SHARED_DIR / "scripts/finding_schema.py"


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class RunStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        if not STORE_PATH.exists():
            self.skipTest("run_store missing")
        self.rs = _load("qb_run_store_under_test", STORE_PATH)
        self.schema = _load("qb_finding_schema_for_store_test", SCHEMA_PATH)

    def _finding(self, fid_seed="a"):
        ev = f"src/{fid_seed}.py:1"
        return self.schema.Finding(
            id=self.schema.compute_finding_id("quality", ev, fid_seed),
            category="quality", severity="P2", confidence="medium",
            evidence=ev, rationale="x", suggested_fix="y", fix_strategy="manual")

    def _store(self, d):
        return self.rs.RunStore(Path(d) / self.rs.OUTPUT_DIR_NAME).open()

    def test_layout_and_identifier_check(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            store.write_findings([self._finding()])
            store.write_summary({"total_findings": 1})
            self.assertEqual(self.rs.validate_store_layout(store.root), [])
            mis = self.rs.validate_store_layout(Path(d) / "Wrong-Name")
            self.assertTrue(any("invalid_store_dir_name" in e for e in mis))

    def test_findings_round_trip_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            store.write_findings([self._finding("b"), self._finding("a")])
            ids = [f["id"] for f in store.read_findings()]
            self.assertEqual(ids, sorted(ids))

    def test_evidence_redaction_and_handle_rule(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            token = "ghp_" + "A" * 30
            store.record_evidence({"finding_id": "QBF-1", "outcome": "kept",
                                   "rollback_handle": "abc123", "after_output": f"leak {token}"})
            store.record_evidence({"finding_id": "QBF-2", "outcome": "kept",
                                   "rollback_handle": "", "after_output": "fine"})
            records = {r["finding_id"]: r for r in store.read_evidence()}
            self.assertNotIn(token, records["QBF-1"]["after_output"])  # redacted
            self.assertIn("<redacted>", records["QBF-1"]["after_output"])
            self.assertEqual(records["QBF-1"]["outcome"], "kept")
            # kept without a handle is downgraded to not-kept (unrecoverable)
            self.assertEqual(records["QBF-2"]["outcome"], "not-kept")
            self.assertEqual(records["QBF-2"]["reason"], "missing-rollback-handle")

    def test_run_log_is_append_only_and_seq_ordered(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            store.append_log({"event": "policy-evaluated", "verdict": "allowed"})
            store.append_log({"event": "fix-kept"})
            lines = (store.root / self.rs.RUN_LOG_FILENAME).read_text().splitlines()
            seqs = [json.loads(line)["seq"] for line in lines]
            self.assertEqual(seqs, [1, 2])

    def test_overwrite_is_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / self.rs.OUTPUT_DIR_NAME
            self.rs.RunStore(root).open()
            (root / "marker.txt").write_text("x", encoding="utf-8")
            with self.assertRaises(self.rs.RunStoreError):
                self.rs.RunStore(root).open()              # refuses to clobber
            self.rs.RunStore(root).open(overwrite=True)    # explicit opt-in

    def test_summary_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            store.write_summary({"note": "key ghp_" + "B" * 30})
            self.assertNotIn("ghp_" + "B" * 30, store.read_summary()["note"])


if __name__ == "__main__":
    unittest.main()
