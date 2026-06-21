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
            out = Path(d) / ".qb/audit"
            code = self.hl.run_headless(repo, output_dir=out)
            self.assertEqual(code, self.hl.EXIT_CLEAN)

    def test_findings_repo_exits_findings_and_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            token = "ghp_" + "A" * 30
            (repo / "leak.txt").write_text(f"key = {token}\n", encoding="utf-8")
            out = Path(d) / ".qb/audit"
            code = self.hl.run_headless(repo, output_dir=out)
            self.assertEqual(code, self.hl.EXIT_FINDINGS)

            # full store + reports present, including the per-run telemetry and the
            # multi-run aggregate series the run path now persists (REQUIRED_SUBPATHS).
            for name in ("findings.jsonl", "evidence", "run-log.jsonl", "summary.json",
                         "report.json", "report.sarif", "summary.txt",
                         "telemetry.json", "telemetry-aggregate.json"):
                self.assertTrue((out / name).exists(), f"missing output: {name}")

            # the aggregate carries this run's record (not just an empty series).
            aggregate = json.loads((out / "telemetry-aggregate.json").read_text())
            self.assertGreaterEqual(len(aggregate.get("runs", [])), 1,
                                    "headless run did not append its telemetry to the aggregate series")

            report = json.loads((out / "report.json").read_text())
            self.assertIn("provenance", report)
            self.assertTrue(report["findings"], "expected findings in report")

            # redaction: the secret value never reaches any output file
            for name in ("findings.jsonl", "report.json", "summary.txt"):
                self.assertNotIn(token, (out / name).read_text())

    def test_crashing_analyzer_is_isolated(self) -> None:
        # A single analyzer raising must NOT abort the whole headless run: the audit
        # completes on the surviving analyzers, logs an `analyzer-error` event, and
        # names the crashed analyzer in summary.analyzers_skipped with its exception
        # type/message as the reason. Without run_headless's own per-analyzer
        # try/except this falls through to the fail-closed handler -> EXIT_INTERNAL_ERROR
        # with zero findings and no per-analyzer attribution (the removal test).
        ai = _load("qb_analyzer_interface_for_headless",
                   SHARED_DIR / "scripts/analyzer_interface.py")

        class _BoomAnalyzer:
            descriptor = ai.AnalyzerDescriptor(id="boom", categories=("quality",), offline=True)

            def analyze(self, repo_root, config):
                raise RuntimeError("boom went off")

        original = self.hl._audit.build_default_registry

        def _registry_with_boom():
            registry = original()
            registry.register(_BoomAnalyzer())
            return registry

        self.hl._audit.build_default_registry = _registry_with_boom
        try:
            with tempfile.TemporaryDirectory() as d:
                repo = Path(d) / "repo"
                repo.mkdir()
                (repo / "readme.md").write_text("# nothing actionable\n", encoding="utf-8")
                (repo / "LICENSE").write_text(_LICENSE_TEXT, encoding="utf-8")
                out = Path(d) / ".qb/audit"
                code = self.hl.run_headless(repo, output_dir=out)
                # The run completes on the surviving analyzers, NOT EXIT_INTERNAL_ERROR.
                self.assertEqual(code, self.hl.EXIT_CLEAN)
                summary = json.loads((out / "summary.json").read_text())
                skipped = {s["id"]: s["reason"] for s in summary["analyzers_skipped"]}
                self.assertIn("boom", skipped)
                self.assertTrue(skipped["boom"].startswith("RuntimeError:"),
                                f"unexpected skip reason: {skipped['boom']!r}")
                self.assertNotIn("boom", summary["analyzers_run"])
                # The failure is attributed in the run log.
                events = [json.loads(line)
                          for line in (out / "run-log.jsonl").read_text().splitlines()
                          if line.strip()]
                boom_errors = [e for e in events
                               if e.get("event") == "analyzer-error" and e.get("analyzer") == "boom"]
                self.assertEqual(len(boom_errors), 1)
                self.assertIn("boom went off", boom_errors[0].get("error", ""))
        finally:
            self.hl._audit.build_default_registry = original

    def test_self_audit_on_qb_repo_yields_documented_exit_code(self) -> None:
        # Phase 7.3: "QB audits QB" must be a repeatable run that produces the
        # findings inventory with a DOCUMENTED exit code (0 clean / 1 findings) when
        # run against this repository -- never a boundary (2) or internal-error (3)
        # code. This pins the `self-audit` Make target's end-to-end behavior.
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / ".qb/audit"
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
            audit = Path(d) / ".qb/audit"
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
            empty = Path(d) / "empty" / ".qb" / "audit"
            empty.mkdir(parents=True)
            code = sig.main(["--root", str(repo), "--out", str(empty),
                             "--scripts-dir", str(SHARED_DIR / "scripts")])
            self.assertEqual(code, sig.GATE_DENIED)

    def test_main_returns_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            (repo / "ok.txt").write_text("clean\n", encoding="utf-8")
            (repo / "LICENSE").write_text(_LICENSE_TEXT, encoding="utf-8")
            code = self.hl.main(["--root", str(repo), "--out", str(Path(d) / ".qb/audit")])
            self.assertEqual(code, self.hl.EXIT_CLEAN)


if __name__ == "__main__":
    unittest.main()
