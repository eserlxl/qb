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

from tests.qb_monorepo import REPO_ROOT, SHARED_DIR

STORE_PATH = SHARED_DIR / "scripts/run_store.py"
SCHEMA_PATH = SHARED_DIR / "scripts/finding_schema.py"
ROUNDTRIP_FIXTURE = REPO_ROOT / "tests/fixtures/findings_roundtrip.jsonl"


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

    def _write_aggregate(self, store) -> None:
        record = self.rs._telemetry_aggregate.build_aggregate([])
        (store.root / self.rs.AGGREGATE_TELEMETRY_FILENAME).write_text(
            json.dumps(record, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_roundtrip_fixture_findings_survive_write_read(self) -> None:
        # The committed multi-category findings fixture round-trips through the store:
        # every record stays conformant and all ids are preserved.
        lines = [ln for ln in ROUNDTRIP_FIXTURE.read_text(encoding="utf-8").splitlines()
                 if ln.strip()]
        findings = [self.schema.Finding.from_dict(json.loads(ln)) for ln in lines]
        self.assertGreaterEqual(len(findings), 5)
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            store.write_findings(findings)
            back = store.read_findings()
        self.assertEqual(sorted(f.id for f in findings), sorted(b["id"] for b in back))
        for b in back:
            self.assertEqual(self.schema.validate_finding(b), [], b)

    def test_layout_and_identifier_check(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            store.write_findings([self._finding()])
            store.write_summary({"total_findings": 1})
            store.write_telemetry({"schema_version": 1, "run_id": "r1"})
            self._write_aggregate(store)
            self.assertEqual(self.rs.validate_store_layout(store.root), [])
            mis = self.rs.validate_store_layout(Path(d) / "Wrong-Name")
            self.assertTrue(any("invalid_store_dir_name" in e for e in mis))

    def test_layout_requires_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            store.write_findings([self._finding()])
            store.write_summary({"total_findings": 1})
            errors = self.rs.validate_store_layout(store.root)
            self.assertIn(f"missing_store_path={self.rs.TELEMETRY_FILENAME}", errors)

    def test_layout_requires_aggregate_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            store.write_findings([self._finding()])
            store.write_summary({"total_findings": 1})
            store.write_telemetry({"schema_version": 1, "run_id": "r1"})
            errors = self.rs.validate_store_layout(store.root)
            self.assertIn(f"missing_store_path={self.rs.AGGREGATE_TELEMETRY_FILENAME}", errors)
            self._write_aggregate(store)
            self.assertEqual(self.rs.validate_store_layout(store.root), [])

    def test_append_telemetry_aggregate_satisfies_layout_and_accumulates(self) -> None:
        # The run paths emit telemetry.json + append the run into the multi-run series;
        # append_telemetry_aggregate is what makes a real run store satisfy its own
        # REQUIRED_SUBPATHS layout, and the series accumulates one entry per run.
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            store.write_findings([self._finding()])
            store.write_summary({"total_findings": 1})
            store.write_telemetry({"schema_version": 1, "run_id": "r1"})
            # write_telemetry alone leaves the aggregate absent (the gap this fixes).
            self.assertIn(f"missing_store_path={self.rs.AGGREGATE_TELEMETRY_FILENAME}",
                          self.rs.validate_store_layout(store.root))
            store.append_telemetry_aggregate({"schema_version": 1, "run_id": "r1"})
            self.assertEqual(self.rs.validate_store_layout(store.root), [])
            agg_path = store.root / self.rs.AGGREGATE_TELEMETRY_FILENAME
            first = self.rs._telemetry_aggregate.read_aggregate(agg_path)
            self.assertEqual([r["run_id"] for r in first["runs"]], ["r1"])
            # a second, differing run appends a second entry (same run_id replaces in place).
            store.append_telemetry_aggregate({"schema_version": 1, "run_id": "r2"})
            second = self.rs._telemetry_aggregate.read_aggregate(agg_path)
            self.assertEqual([r["run_id"] for r in second["runs"]], ["r1", "r2"])

    def test_append_telemetry_aggregate_requires_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            with self.assertRaises(self.rs.RunStoreError):
                store.append_telemetry_aggregate({"run_id": "no-version"})

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

    def test_findings_redacted(self) -> None:
        # write_findings must redact secret-shaped material in any field, like the
        # other writers; the findings file is not exempt from the no-secret invariant.
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            token = "ghp_" + "C" * 30
            f = self.schema.Finding(
                id=self.schema.compute_finding_id("secret", "src/x.py:1", "k"),
                category="secret", severity="P1", confidence="high",
                evidence="src/x.py:1",
                rationale=f"a length-bounded pattern matched value {token} here",
                suggested_fix="remove it and rotate", fix_strategy="manual")
            store.write_findings([f])
            raw = (store.root / self.rs.FINDINGS_FILENAME).read_text(encoding="utf-8")
            self.assertNotIn(token, raw)
            self.assertIn("<redacted>", raw)
            # round-trip still parses and preserves the id
            self.assertEqual([r["id"] for r in store.read_findings()], [f.id])

    def test_record_evidence_requires_finding_id(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            with self.assertRaises(self.rs.RunStoreError):
                store.record_evidence({"outcome": "reverted"})  # no finding_id -> not unknown.json

    def test_record_evidence_refuses_to_clobber(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            store.record_evidence({"finding_id": "QBF-dup", "outcome": "reverted"})
            with self.assertRaises(self.rs.RunStoreError):
                store.record_evidence({"finding_id": "QBF-dup", "outcome": "kept",
                                       "rollback_handle": "h"})

    def test_overwrite_clears_stale_evidence(self) -> None:
        # A fresh (overwrite=True) run must clear stale evidence/ so the clobber guard
        # does not abort a re-run over the same output dir on a leftover record.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / self.rs.OUTPUT_DIR_NAME
            self.rs.RunStore(root).open().record_evidence(
                {"finding_id": "QBF-stale", "outcome": "reverted"})
            store2 = self.rs.RunStore(root).open(overwrite=True)
            store2.record_evidence({"finding_id": "QBF-stale", "outcome": "reverted"})  # no clobber
            self.assertEqual(len(store2.read_evidence()), 1)

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

    def test_write_telemetry_is_deterministic_and_requires_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            store.write_telemetry({"schema_version": 1, "run_id": "r1", "quality": {"fix_safety_ok": True}})
            raw = (store.root / self.rs.TELEMETRY_FILENAME).read_text(encoding="utf-8")
            self.assertTrue(raw.endswith("\n"))
            self.assertEqual(raw, json.dumps({
                "quality": {"fix_safety_ok": True},
                "run_id": "r1",
                "schema_version": 1,
            }, sort_keys=True, indent=2) + "\n")
            with self.assertRaises(self.rs.RunStoreError):
                store.write_telemetry({"run_id": "missing-version"})

    def test_read_telemetry_round_trip_absent_and_version_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            self.assertEqual(store.read_telemetry(), {})
            record = {"schema_version": 1, "run_id": "r1", "quality": {"fix_safety_ok": True}}
            store.write_telemetry(record)
            self.assertEqual(store.read_telemetry(), record)
            (store.root / self.rs.TELEMETRY_FILENAME).write_text(
                json.dumps({"schema_version": 999, "run_id": "old"}) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(store.read_telemetry(), {})
            (store.root / self.rs.TELEMETRY_FILENAME).write_text("{not-json\n", encoding="utf-8")
            self.assertEqual(store.read_telemetry(), {})

    def test_load_prior_telemetry_uses_prior_store_directory_convention(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            prior = self.rs.RunStore(Path(d) / "previous" / self.rs.OUTPUT_DIR_NAME).open()
            record = {"schema_version": 1, "run_id": "previous", "quality": {"fix_safety_ok": True}}
            prior.write_telemetry(record)
            self.assertEqual(self.rs.load_prior_telemetry(prior.root), record)
            self.assertEqual(self.rs.load_prior_telemetry(Path(d) / "missing" / self.rs.OUTPUT_DIR_NAME), {})
            self.assertEqual(self.rs.load_prior_telemetry(None), {})

    def test_write_telemetry_redacts_secret_shaped_values(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            token = "ghp_" + "D" * 30
            store.write_telemetry({
                "schema_version": 1,
                "run_id": "r1",
                "quality": {"rationale": f"category carried {token}"},
            })
            raw = (store.root / self.rs.TELEMETRY_FILENAME).read_text(encoding="utf-8")
            self.assertNotIn(token, raw)
            self.assertIn("<redacted>", raw)
            self.assertEqual(store.read_telemetry()["quality"]["rationale"], "category carried <redacted>")


if __name__ == "__main__":
    unittest.main()
