"""Phase 6.3 -- headless CLI + exit-code contract.

Pins: the non-interactive audit->report loop writes the full store + reports to the
fixed-name output directory; the exit code follows the contract (clean repo -> 0,
findings -> 1); the report validates; no secret leaks into output; and the run is
offline + dependency-light (stdlib only).
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR, REPO_ROOT

MODULE_PATH = SHARED_DIR / "scripts/qb_headless.py"

# A genuinely clean repo declares its distribution terms; fixtures that assert an
# EXIT_CLEAN run include this so the license-hygiene analyzer has nothing to flag.
_LICENSE_TEXT = (
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


class HeadlessTests(unittest.TestCase):
    def setUp(self) -> None:
        if not MODULE_PATH.exists():
            self.skipTest("qb_headless missing")
        self.hl = _load("qb_headless_under_test", MODULE_PATH)

    def test_clean_repo_exits_clean(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            (repo / "readme.md").write_text("# nothing actionable here\n", encoding="utf-8")
            (repo / "LICENSE").write_text(_LICENSE_TEXT, encoding="utf-8")
            out = Path(d) / "QB-Audit"
            code = self.hl.run_headless(repo, output_dir=out)
            self.assertEqual(code, self.hl.EXIT_CLEAN)

    def test_findings_repo_exits_findings_and_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            token = "ghp_" + "A" * 30
            (repo / "leak.txt").write_text(f"key = {token}\n", encoding="utf-8")
            out = Path(d) / "QB-Audit"
            code = self.hl.run_headless(repo, output_dir=out)
            self.assertEqual(code, self.hl.EXIT_FINDINGS)

            # full store + reports present
            for name in ("findings.jsonl", "evidence", "run-log.jsonl", "summary.json",
                         "report.json", "report.sarif", "summary.txt"):
                self.assertTrue((out / name).exists(), f"missing output: {name}")

            report = json.loads((out / "report.json").read_text())
            self.assertIn("provenance", report)
            self.assertTrue(report["findings"], "expected findings in report")

            # redaction: the secret value never reaches any output file
            for name in ("findings.jsonl", "report.json", "summary.txt"):
                self.assertNotIn(token, (out / name).read_text())

    def test_self_audit_on_qb_repo_yields_documented_exit_code(self) -> None:
        # Phase 7.3: "QB audits QB" must be a repeatable run that produces the
        # findings inventory with a DOCUMENTED exit code (0 clean / 1 findings) when
        # run against this repository -- never a boundary (2) or internal-error (3)
        # code. This pins the `self-audit` Make target's end-to-end behavior.
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "QB-Audit"
            code = self.hl.run_headless(REPO_ROOT, output_dir=out)
            self.assertIn(code, (self.hl.EXIT_CLEAN, self.hl.EXIT_FINDINGS),
                          f"self-audit returned non-documented exit code {code}")
            self.assertTrue((out / "findings.jsonl").exists(),
                            "self-audit did not produce findings.jsonl")

    def test_production_gate_entrypoint_reports_decision(self) -> None:
        # Phase 7.4: the production-gate decision is reachable through a dedicated
        # entrypoint with a documented exit code (0 passed / 1 denied), not only an
        # in-test call.
        sig = _load("qb_production_gate_signals_for_headless",
                    SHARED_DIR / "scripts/production_gate_signals.py")
        store = _load("qb_run_store_for_headless", SHARED_DIR / "scripts/run_store.py")
        recov = _load("qb_recoverability_for_headless", SHARED_DIR / "scripts/recoverability_drill.py")
        with tempfile.TemporaryDirectory() as d:
            audit = Path(d) / "QB-Audit"
            rs = store.RunStore(audit).open()
            rs.write_telemetry({"schema_version": 1,
                                "quality": {"precision_estimate": 0.95, "fix_safety_ok": True}})
            rs.write_findings([])
            recov.persist_evidence(
                {"schema_version": 1, "run_id": "r", "baseline_ref": "refs/qb-baseline/r",
                 "baseline_sha_len": 40, "baseline_clean": True, "passed": True}, audit)
            repo = Path(d) / "repo"
            repo.mkdir()
            code = sig.main(["--root", str(repo), "--out", str(audit),
                             "--scripts-dir", str(SHARED_DIR / "scripts")])
            self.assertEqual(code, sig.GATE_PASSED)
            # An empty store denies (fail-closed) with a documented non-zero code.
            empty = Path(d) / "empty-QB-Audit"
            empty.mkdir()
            code = sig.main(["--root", str(repo), "--out", str(empty),
                             "--scripts-dir", str(SHARED_DIR / "scripts")])
            self.assertEqual(code, sig.GATE_DENIED)

    def test_main_returns_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            (repo / "ok.txt").write_text("clean\n", encoding="utf-8")
            (repo / "LICENSE").write_text(_LICENSE_TEXT, encoding="utf-8")
            code = self.hl.main(["--root", str(repo), "--out", str(Path(d) / "QB-Audit")])
            self.assertEqual(code, self.hl.EXIT_CLEAN)


if __name__ == "__main__":
    unittest.main()
