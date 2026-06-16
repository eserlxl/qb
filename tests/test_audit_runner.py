"""Conformance test for the audit runner + output convention (Phase 1.4).

Pins: deterministic byte-identical output across runs; aggregation of the
reference + secret-hygiene analyzers' findings; the total ordering; the
offline-by-default rule (networked analyzers skipped with a reason); the fixed
output-directory identifier check; redaction; and the read-only obligation on the
audited tree.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

MODULE_PATH = SHARED_DIR / "scripts/audit_runner.py"

DEFAULT_OFF_NETWORKED_AUDIT = {
    "stub": "net-stub is registered with offline=False",
    "asserted": (
        "default AnalyzerConfig leaves net-stub out of analyzers_run",
        "analyzers_skipped records id=net-stub",
        "analyzers_skipped records reason=networked-disabled",
    ),
    "gap": "closed: the toggle test now asserts total_findings/category_counts are unaffected by the skipped stub",
}

EXPLICIT_ALLOW_NETWORKED_AUDIT = {
    "stub": "net-stub is registered with offline=False and AnalyzerConfig(allow_networked=True)",
    "asserted": ("enabled summary includes net-stub in analyzers_run",),
    "gap": "closed: the toggle test now asserts allow_networked true and no networked-disabled skip for net-stub",
}

NETWORKED_POLICY_INVARIANT_NOTE = {
    "network": "the networked analyzer under test is the in-memory _networked_stub; it performs no I/O",
    "mutation_guard": "test_runner_does_not_mutate_the_audited_tree is the read-only guard for this slice",
}


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _networked_stub(runner, *, emit=False):
    class _Net:
        descriptor = runner.AnalyzerDescriptor(id="net-stub", categories=("dependency",), offline=False)

        def analyze(self, repo_root, config):
            if emit:
                evidence = "deps.txt:1"
                return [runner._ai.Finding(
                    id=runner._ai.compute_finding_id("dependency", evidence, "net-stub"),
                    category="dependency", severity="P2", confidence="medium",
                    evidence=evidence, rationale="networked stub finding",
                    suggested_fix="review dependency signal", fix_strategy="manual",
                )]
            return []

    return _Net()


def _make_fixture(root: Path) -> None:
    (root / "clean.txt").write_text("nothing to see here\n", encoding="utf-8")
    token = "ghp_" + "F" * 30  # github_legacy_pat; split so it is not a committed literal
    (root / "leak.txt").write_text(f"api_key = {token}\n", encoding="utf-8")


def _git_init(path: Path) -> None:
    if shutil.which("git") is None:
        raise unittest.SkipTest("git not available")
    subprocess.run(["git", "init"], cwd=str(path), text=True, capture_output=True, check=True)


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
            self.assertTrue(any(f.category == "secret" and f.evidence.startswith("leak.txt:") for f in findings),
                            "secret-hygiene finding missing")
            # the no-op reference analyzer is not in the real default registry
            self.assertFalse(any(f.evidence == ".:1" for f in findings),
                             "reference no-op finding should not appear in a real audit")
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
            reg.register(_networked_stub(self.runner, emit=True))

            offline = self.runner.run_audit(
                repo, config=self.runner.AnalyzerConfig(), registry=reg,
                output_dir=Path(d) / "off" / self.runner.OUTPUT_DIR_NAME,
            )["summary"]
            self.assertFalse(offline["allow_networked"])
            self.assertNotIn("net-stub", offline["analyzers_run"])
            self.assertEqual(
                offline["analyzers_skipped"],
                sorted(offline["analyzers_skipped"], key=lambda item: item["id"]),
            )
            self.assertTrue(any(s["id"] == "net-stub" and s["reason"] == "networked-disabled"
                                for s in offline["analyzers_skipped"]))
            self.assertEqual(offline["total_findings"], 1)
            self.assertNotIn("dependency", offline["category_counts"])

            reg2 = self.runner.AnalyzerRegistry()
            reg2.register(self.runner.ReferenceAnalyzer())
            reg2.register(_networked_stub(self.runner, emit=True))
            enabled = self.runner.run_audit(
                repo, config=self.runner.AnalyzerConfig(allow_networked=True), registry=reg2,
                output_dir=Path(d) / "on" / self.runner.OUTPUT_DIR_NAME,
            )["summary"]
            self.assertTrue(enabled["allow_networked"])
            self.assertIn("net-stub", enabled["analyzers_run"])
            self.assertFalse(any(s["id"] == "net-stub" and s["reason"] == "networked-disabled"
                                 for s in enabled["analyzers_skipped"]))
            self.assertEqual(enabled["category_counts"].get("dependency"), 1)

            reg3 = self.runner.AnalyzerRegistry()
            reg3.register(self.runner.ReferenceAnalyzer())
            reg3.register(_networked_stub(self.runner, emit=True))
            enabled_again = self.runner.run_audit(
                repo, config=self.runner.AnalyzerConfig(allow_networked=True), registry=reg3,
                output_dir=Path(d) / "on-again" / self.runner.OUTPUT_DIR_NAME,
            )["summary"]
            self.assertEqual(enabled, enabled_again)

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

    def test_gitignored_qb_artifacts_are_not_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            _git_init(repo)
            (repo / ".gitignore").write_text(".qb/\n", encoding="utf-8")
            (repo / ".qb").mkdir()
            ignored_token = "ghp_" + "I" * 30
            (repo / ".qb" / "ignored.py").write_text(
                f"api_key = '{ignored_token}'\nsubprocess.run(cmd, shell=True)\n",
                encoding="utf-8",
            )
            visible_token = "ghp_" + "V" * 30
            (repo / "leak.txt").write_text(f"api_key = {visible_token}\n", encoding="utf-8")

            registry = self.runner.AnalyzerRegistry()
            registry.register(self.runner.SecretHygieneAnalyzer())
            registry.register(self.runner.CommandInjectionAnalyzer())
            result = self.runner.run_audit(
                repo,
                registry=registry,
                output_dir=Path(d) / "out" / self.runner.OUTPUT_DIR_NAME,
            )
            evidences = [finding.evidence for finding in result["findings"]]

            self.assertTrue(any(evidence.startswith("leak.txt:") for evidence in evidences), evidences)
            self.assertFalse(any(evidence.startswith(".qb/") for evidence in evidences), evidences)
            findings_text = (
                Path(result["output_dir"]) / self.runner.FINDINGS_FILENAME
            ).read_text(encoding="utf-8")
            self.assertNotIn(ignored_token, findings_text)


if __name__ == "__main__":
    unittest.main()
