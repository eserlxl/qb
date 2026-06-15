"""Conformance test for the audit runner + output convention (Phase 1.4).

Pins: deterministic byte-identical output across runs; aggregation of the
reference + secret-hygiene analyzers' findings; the total ordering; the
offline-by-default rule (networked analyzers skipped with a reason); the fixed
output-directory identifier check; redaction; and the read-only obligation on the
audited tree.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

MODULE_PATH = SHARED_DIR / "scripts/audit_runner.py"


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _networked_stub(runner):
    class _Net:
        descriptor = runner.AnalyzerDescriptor(id="net-stub", categories=("dependency",), offline=False)

        def analyze(self, repo_root, config):
            return []

    return _Net()


def _make_fixture(root: Path) -> None:
    (root / "clean.txt").write_text("nothing to see here\n", encoding="utf-8")
    token = "ghp_" + "F" * 30  # github_legacy_pat; split so it is not a committed literal
    (root / "leak.txt").write_text(f"api_key = {token}\n", encoding="utf-8")


class AuditRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        if not MODULE_PATH.exists():
            self.skipTest(f"audit runner missing: {MODULE_PATH}")
        self.runner = _load("qb_audit_runner_under_test", MODULE_PATH)

    def test_run_is_deterministic_across_two_runs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            _make_fixture(repo)
            out_a = Path(d) / "a" / self.runner.OUTPUT_DIR_NAME
            out_b = Path(d) / "b" / self.runner.OUTPUT_DIR_NAME
            self.runner.run_audit(repo, output_dir=out_a)
            self.runner.run_audit(repo, output_dir=out_b)
            a = (out_a / self.runner.FINDINGS_FILENAME).read_bytes()
            b = (out_b / self.runner.FINDINGS_FILENAME).read_bytes()
            self.assertEqual(a, b, "two runs over an unchanged repo must be byte-identical")

    def test_aggregates_reference_and_secret_findings_conformant_and_redacted(self) -> None:
        token = "ghp_" + "F" * 30
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            _make_fixture(repo)
            out = Path(d) / "out" / self.runner.OUTPUT_DIR_NAME
            result = self.runner.run_audit(repo, output_dir=out)
            findings = result["findings"]

            for f in findings:
                self.assertEqual(self.runner.validate_finding(f), [], f"non-conformant: {f}")
            self.assertTrue(any(f.category == "config" and f.evidence == ".:1" for f in findings),
                            "reference analyzer finding missing")
            self.assertTrue(any(f.category == "secret" and f.evidence.startswith("leak.txt:") for f in findings),
                            "secret-hygiene finding missing")
            findings_text = (out / self.runner.FINDINGS_FILENAME).read_text(encoding="utf-8")
            self.assertNotIn(token, findings_text, "secret value must be redacted from output")

    def test_findings_are_totally_ordered_by_severity(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            _make_fixture(repo)
            out = Path(d) / "out" / self.runner.OUTPUT_DIR_NAME
            findings = self.runner.run_audit(repo, output_dir=out)["findings"]
            keys = [self.runner._sort_key(f) for f in findings]
            self.assertEqual(keys, sorted(keys), "findings must be emitted in total order")

    def test_offline_by_default_skips_networked_analyzer(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            _make_fixture(repo)

            reg = self.runner.AnalyzerRegistry()
            reg.register(self.runner.ReferenceAnalyzer())
            reg.register(_networked_stub(self.runner))

            offline = self.runner.run_audit(
                repo, config=self.runner.AnalyzerConfig(), registry=reg,
                output_dir=Path(d) / "off" / self.runner.OUTPUT_DIR_NAME,
            )["summary"]
            self.assertNotIn("net-stub", offline["analyzers_run"])
            self.assertTrue(any(s["id"] == "net-stub" and s["reason"] == "networked-disabled"
                                for s in offline["analyzers_skipped"]))

            reg2 = self.runner.AnalyzerRegistry()
            reg2.register(self.runner.ReferenceAnalyzer())
            reg2.register(_networked_stub(self.runner))
            enabled = self.runner.run_audit(
                repo, config=self.runner.AnalyzerConfig(allow_networked=True), registry=reg2,
                output_dir=Path(d) / "on" / self.runner.OUTPUT_DIR_NAME,
            )["summary"]
            self.assertIn("net-stub", enabled["analyzers_run"])

    def test_output_identifier_check(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            _make_fixture(repo)
            out = Path(d) / "out" / self.runner.OUTPUT_DIR_NAME
            self.runner.run_audit(repo, output_dir=out)
            self.assertEqual(self.runner.validate_output_layout(out), [])

            misnamed = Path(d) / "out" / "Audit-Output"
            errors = self.runner.validate_output_layout(misnamed)
            self.assertTrue(any("invalid_output_dir_name" in e for e in errors), errors)

            empty = Path(d) / "empty" / self.runner.OUTPUT_DIR_NAME
            empty.mkdir(parents=True)
            self.assertTrue(any("missing_output_file" in e for e in self.runner.validate_output_layout(empty)))

    def test_runner_does_not_mutate_the_audited_tree(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            _make_fixture(repo)
            before = {p.name: p.stat().st_mtime_ns for p in repo.iterdir()}
            # Output written OUTSIDE the audited tree.
            self.runner.run_audit(repo, output_dir=Path(d) / "out" / self.runner.OUTPUT_DIR_NAME)
            after = {p.name: p.stat().st_mtime_ns for p in repo.iterdir()}
            self.assertEqual(before, after, "the audited tree must be unchanged after a run")


if __name__ == "__main__":
    unittest.main()
