"""Conformance test for the audit runner + output convention (Phase 1.4).

Pins: deterministic byte-identical output across runs; aggregation of the
reference + secret-hygiene analyzers' findings; the total ordering; the
offline-by-default rule (networked analyzers skipped with a reason); the fixed
output-directory identifier check; redaction; and the read-only obligation on the
audited tree.
"""

from __future__ import annotations

import importlib.util
import json
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

NETWORKED_POLICY_SYNC_NOTE = (
    "After networked-policy shared/runtime changes land, run scripts/sync.sh, then "
    "scripts/sync.sh --check; antigravity is planning-only and intentionally excluded."
)

COMBINED_FAIL_CLOSED_GUARD_DECISION = {
    "home": "tests/test_audit_runner.py::test_combined_fail_closed_policy_defaults",
    "shape": "one named test composes the optional-tool-absent and networked-default/allow stubs",
    "reuse": "uses analyzer_quality.ToolAdapter for optional-tool absence and _networked_stub for networked policy",
}

COMBINED_GUARD_ENGINE_INVARIANTS = {
    "dependency_free": "validated by python3 -m unittest tests.test_least_privilege",
    "deterministic": "test_run_is_deterministic_across_two_runs stays green",
    "read_only": "test_runner_does_not_mutate_the_audited_tree stays green",
    "side_effects": "combined guard uses only in-memory/nonexistent-tool stubs; no network call or install",
}

COMBINED_GUARD_SYNC_NOTE = (
    "After combined-guard shared/runtime changes land, run scripts/sync.sh, then "
    "scripts/sync.sh --check; antigravity is planning-only and intentionally excluded."
)


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


def _unreachable_networked_stub(runner):
    class _NetBroken:
        descriptor = runner.AnalyzerDescriptor(id="net-unreachable", categories=("dependency",), offline=False)

        def analyze(self, repo_root, config):
            raise RuntimeError("enrichment source unreachable")

    return _NetBroken()


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

    def test_run_summary_aggregates_adapter_capability_and_is_exit_neutral(self) -> None:
        # The run summary must aggregate each analyzer's adapter-level capability
        # (e.g. ruff/pyflakes ran vs skipped) at the run level so an absent optional
        # tool is reported, not silently dropped; and an absent tool must not change
        # the run outcome (graceful degradation). A stub makes the absent-tool path
        # deterministic regardless of which tools this host actually has installed.
        runner = self.runner

        class _CapStub:
            def __init__(self) -> None:
                self.descriptor = runner.AnalyzerDescriptor(
                    id="cap-stub", categories=("quality",), offline=True
                )
                self.last_capability_report = {
                    "ran": ["present-tool"],
                    "skipped": [{"adapter": "absent-tool", "reason": "tool-unavailable"}],
                }

            def analyze(self, repo_root, config):
                return []

        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            reg = runner.AnalyzerRegistry()
            reg.register(_CapStub())
            summary = runner.run_audit(
                repo, config=runner.AnalyzerConfig(), registry=reg,
                output_dir=Path(d) / runner.OUTPUT_DIR_NAME,
            )["summary"]

        self.assertIn("capability_report", summary)
        self.assertEqual(
            summary["capability_report"]["cap-stub"],
            {
                "ran": ["present-tool"],
                "skipped": [{"adapter": "absent-tool", "reason": "tool-unavailable"}],
            },
        )
        # Exit-code neutrality: the absent optional tool produced no finding and did
        # not error the run -- the run is clean (0 findings), exactly as it would be
        # had the tool been present and reported nothing.
        self.assertEqual(summary["total_findings"], 0)
        self.assertNotIn("cap-stub", [s["id"] for s in summary["analyzers_skipped"]])

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

    def test_command_suppression_report_is_written_to_summary(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            (repo / "suppressed.py").write_text(
                "import os\n"
                "# qb-ignore: system-shell-call fixture exercises a documented false-positive control\n"
                "os.system(cmd)\n",
                encoding="utf-8",
            )
            registry = self.runner.AnalyzerRegistry()
            registry.register(self.runner.CommandInjectionAnalyzer())
            out = Path(d) / "out" / self.runner.OUTPUT_DIR_NAME
            result = self.runner.run_audit(repo, registry=registry, output_dir=out)

            expected = [{
                "id": "command-injection",
                "rule": "system-shell-call",
                "evidence": "suppressed.py:3",
                "reason": "fixture exercises a documented false-positive control",
            }]
            self.assertEqual(result["findings"], [])
            self.assertEqual(result["summary"]["analyzers_suppressed"], expected)
            summary = json.loads((out / self.runner.SUMMARY_FILENAME).read_text(encoding="utf-8"))
            self.assertEqual(summary["analyzers_suppressed"], expected)

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

    def test_enabled_unreachable_networked_analyzer_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            _make_fixture(repo)

            reg = self.runner.AnalyzerRegistry()
            reg.register(self.runner.ReferenceAnalyzer())
            reg.register(_unreachable_networked_stub(self.runner))
            result = self.runner.run_audit(
                repo, config=self.runner.AnalyzerConfig(allow_networked=True), registry=reg,
                output_dir=Path(d) / "unreachable" / self.runner.OUTPUT_DIR_NAME,
            )

        summary = result["summary"]
        self.assertTrue(summary["allow_networked"])
        self.assertNotIn("net-unreachable", summary["analyzers_run"])
        self.assertTrue(any(
            s["id"] == "net-unreachable" and "RuntimeError: enrichment source unreachable" in s["reason"]
            for s in summary["analyzers_skipped"]
        ))
        self.assertEqual(summary["total_findings"], 1)  # reference finding only; no fabricated dependency
        self.assertNotIn("dependency", summary["category_counts"])

    def test_combined_fail_closed_policy_defaults(self) -> None:
        """Optional tools degrade when absent; networked analyzers stay disabled unless explicitly allowed."""
        quality = self.runner._quality
        missing_optional = quality.ToolAdapter(
            name="missing-pyflakes",
            executable="qb-nonexistent-pyflakes",
            category="correctness",
            build_argv=lambda root: ["qb-nonexistent-pyflakes", root],
            parse=lambda stdout, stderr: [],
        )
        optional_analyzer = quality.QualityAnalyzer([missing_optional])
        with tempfile.TemporaryDirectory() as d:
            try:
                optional_findings = optional_analyzer.analyze(d, None)
            except Exception as exc:  # pragma: no cover - unexpected failure reports context
                self.fail(f"missing optional tool should skip without raising: {exc!r}")
        self.assertEqual(optional_findings, [])
        self.assertEqual(optional_analyzer.last_capability_report["ran"], [])
        self.assertEqual(optional_analyzer.last_capability_report["skipped"], [
            {
                "adapter": "missing-pyflakes",
                "executable": "qb-nonexistent-pyflakes",
                "reason": "tool-unavailable",
            }
        ])

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
            self.assertTrue(any(s["id"] == "net-stub" and s["reason"] == "networked-disabled"
                                for s in offline["analyzers_skipped"]))
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
            self.assertEqual(enabled["category_counts"].get("dependency"), 1)

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
