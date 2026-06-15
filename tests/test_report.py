"""Phase 5.2 -- machine-readable reporting (JSON / SARIF / summary).

Pins: the versioned JSON report (schema-conformant, rendered only from the store),
the SARIF 2.1.0 mapping (category->rule, P0-P3->level, evidence->location), the
severity-to-level table, and the human summary vocabulary.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

REPORT_PATH = SHARED_DIR / "scripts/report.py"
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


class ReportTests(unittest.TestCase):
    def setUp(self) -> None:
        for path in (REPORT_PATH, STORE_PATH, SCHEMA_PATH):
            if not path.exists():
                self.skipTest("report/store/schema missing")
        self.report = _load("qb_report_under_test", REPORT_PATH)
        self.rs = _load("qb_run_store_under_test", STORE_PATH)
        self.schema = _load("qb_finding_schema_for_report_test", SCHEMA_PATH)

    def _populated_store(self, root):
        store = self.rs.RunStore(root).open()
        findings = []
        for cat, sev, seed in (("secret", "P1", "a"), ("quality", "P3", "b")):
            ev = f"src/{seed}.py:{7}"
            findings.append(self.schema.Finding(
                id=self.schema.compute_finding_id(cat, ev, seed),
                category=cat, severity=sev, confidence="high",
                evidence=ev, rationale=f"{cat} issue", suggested_fix="fix it", fix_strategy="manual"))
        store.write_findings(findings)
        store.record_evidence({"finding_id": findings[0].id, "outcome": "reverted",
                               "rollback_handle": "h1", "verify_command": ["make", "test"], "after_exit": 1})
        store.write_summary({"trigger": "completed", "total_findings": 2})
        return store

    def test_json_report_is_schema_conformant_and_from_store(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            store = self._populated_store(Path(d) / self.rs.OUTPUT_DIR_NAME)
            report = self.report.render_json(store)
            self.assertEqual(self.report.validate_report(report), [])
            self.assertEqual(report["schema_version"], self.report.REPORT_SCHEMA_VERSION)
            self.assertEqual(len(report["findings"]), 2)
            self.assertEqual(len(report["hardening"]), 1)
            self.assertEqual(report["hardening"][0]["outcome"], "reverted")

    def test_sarif_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            store = self._populated_store(Path(d) / self.rs.OUTPUT_DIR_NAME)
            sarif = self.report.render_sarif(store)
            self.assertEqual(sarif["version"], "2.1.0")
            self.assertEqual(sarif["runs"][0]["tool"]["driver"]["name"], "QB")
            results = sarif["runs"][0]["results"]
            self.assertEqual(len(results), 2)
            by_rule = {r["ruleId"]: r for r in results}
            self.assertIn("qb/secret", by_rule)
            self.assertEqual(by_rule["qb/secret"]["level"], "error")    # P1 -> error
            self.assertEqual(by_rule["qb/quality"]["level"], "note")    # P3 -> note
            loc = by_rule["qb/secret"]["locations"][0]["physicalLocation"]
            self.assertEqual(loc["artifactLocation"]["uri"], "src/a.py")
            self.assertEqual(loc["region"]["startLine"], 7)

    def test_severity_to_sarif_level_table(self) -> None:
        self.assertEqual(self.report.SEVERITY_TO_SARIF,
                         {"P0": "error", "P1": "error", "P2": "warning", "P3": "note"})

    def test_summary_text_uses_p_vocabulary(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            store = self._populated_store(Path(d) / self.rs.OUTPUT_DIR_NAME)
            text = self.report.render_summary_text(store)
            self.assertIn("P0=", text)
            self.assertIn("P1=1", text)
            self.assertIn("reverted=1", text)

    def test_emit_writes_three_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            store = self._populated_store(Path(d) / self.rs.OUTPUT_DIR_NAME)
            paths = self.report.emit(store)
            for key in ("report", "sarif", "summary_text"):
                self.assertTrue(Path(paths[key]).is_file())
            parsed = json.loads(Path(paths["report"]).read_text())
            self.assertEqual(self.report.validate_report(parsed), [])


if __name__ == "__main__":
    unittest.main()
