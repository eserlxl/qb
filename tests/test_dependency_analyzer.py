"""Phase 2.4 -- dependency & supply-chain analyzer (offline default, opt-in net).

Pins: the offline tier (unpinned dependency + missing-lockfile hygiene findings,
pinned deps clean); the default network-free path (enrichment skipped); opt-in
enrichment with a configured source (CVE evidence + provenance + severity);
fail-closed fallback when the source errors; conformance; determinism; read-only.
No real network is used -- the advisory source is an injected callable.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

MODULE_PATH = SHARED_DIR / "scripts/analyzer_dependency.py"


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _cfg(allow_networked: bool):
    return sys.modules["qb_analyzer_interface"].AnalyzerConfig(allow_networked=allow_networked)


def _fixture(root: Path) -> None:
    (root / "requirements.txt").write_text(
        "# deps\nflask\ndjango==4.2.1\nrequests>=2.0\n", encoding="utf-8"
    )
    (root / "package.json").write_text('{"name": "x", "dependencies": {}}\n', encoding="utf-8")


class DependencyAnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        if not MODULE_PATH.exists():
            self.skipTest(f"analyzer_dependency missing: {MODULE_PATH}")
        self.dep = _load("qb_analyzer_dependency_under_test", MODULE_PATH)
        self.validate = sys.modules["qb_analyzer_interface"].validate_finding

    def test_offline_tier_flags_unpinned_and_missing_lockfile(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            _fixture(Path(d))
            analyzer = self.dep.DependencyAnalyzer()
            findings = analyzer.analyze(d, _cfg(False))

        for f in findings:
            self.assertEqual(self.validate(f), [])
            self.assertEqual(f.category, "dependency")
        rules = {f.id for f in findings}
        self.assertTrue(any("requirements.txt:" in f.evidence for f in findings))
        self.assertTrue(any(f.evidence == "package.json:1" for f in findings), "missing-lockfile expected")
        # flask (unpinned) and requests (>= only) flagged; django==4.2.1 (pinned) not.
        evidences = [f.evidence for f in findings if f.evidence.startswith("requirements.txt")]
        self.assertIn("requirements.txt:2", evidences)   # flask
        self.assertIn("requirements.txt:4", evidences)   # requests >=
        self.assertNotIn("requirements.txt:3", evidences)  # django pinned
        self.assertEqual(analyzer.last_enrichment_status, "skipped:disabled")
        self.assertGreaterEqual(len(rules), 3)

    def test_cargo_toml_unpinned_dependencies_are_flagged(self) -> None:
        # Cargo semantics: a bare "1.0" is a caret range (unpinned); "*" is a
        # wildcard (unpinned); only "=X.Y.Z" is an exact pin (clean).
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            root.joinpath("Cargo.toml").write_text(
                '[dependencies]\n'
                'serde = "1.0"\n'        # line 2: caret -> unpinned
                'rand = "*"\n'           # line 3: wildcard -> unpinned
                'exacted = "=1.2.3"\n'   # line 4: exact -> clean
                '[dev-dependencies]\n'
                'proptest = "^1.0"\n',   # line 6: caret -> unpinned
                encoding="utf-8",
            )
            findings = self.dep.DependencyAnalyzer().analyze(d, _cfg(False))
        cargo = [f.evidence for f in findings if f.evidence.startswith("Cargo.toml")]
        self.assertIn("Cargo.toml:2", cargo)
        self.assertIn("Cargo.toml:3", cargo)
        self.assertIn("Cargo.toml:6", cargo)
        self.assertNotIn("Cargo.toml:4", cargo)  # exact pin is clean
        for finding in findings:
            if finding.evidence.startswith("Cargo.toml"):
                self.assertEqual(finding.category, "dependency")
                self.assertEqual(self.validate(finding), [])

    def test_pyproject_dependencies_are_parsed_offline(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            root.joinpath("pyproject.toml").write_text(
                '[project]\n'
                'dependencies = [\n'
                '  "flask>=3.0",\n'
                '  "django==4.2.1",\n'
                ']\n'
                '[tool.poetry.dependencies]\n'
                'python = "^3.11"\n'
                'requests = "^2.31"\n'
                'urllib3 = "2.2.1"\n',
                encoding="utf-8",
            )
            root.joinpath("package.json").write_text(
                '{\n'
                '  "dependencies": {\n'
                '    "express": "^4.18.0",\n'
                '    "lodash": "4.17.21"\n'
                '  },\n'
                '  "devDependencies": {\n'
                '    "vitest": "latest"\n'
                '  }\n'
                '}\n',
                encoding="utf-8",
            )
            root.joinpath("package-lock.json").write_text(
                '{"lockfileVersion": 3}\n',
                encoding="utf-8",
            )
            analyzer = self.dep.DependencyAnalyzer()
            findings = analyzer.analyze(d, _cfg(False))

        evidences = [f.evidence for f in findings if f.evidence.startswith("pyproject.toml")]
        self.assertIn("pyproject.toml:3", evidences)  # flask>=3.0
        self.assertIn("pyproject.toml:8", evidences)  # requests = "^2.31"
        self.assertNotIn("pyproject.toml:4", evidences)  # django==4.2.1
        self.assertNotIn("pyproject.toml:9", evidences)  # urllib3 = "2.2.1"
        package_evidences = [
            f.evidence for f in findings if f.evidence.startswith("package.json")
        ]
        self.assertIn("package.json:3", package_evidences)  # express ^ range
        self.assertIn("package.json:7", package_evidences)  # vitest latest
        self.assertNotIn("package.json:4", package_evidences)  # lodash exact pin
        self.assertNotIn("package.json:1", package_evidences)  # lockfile present
        for f in findings:
            self.assertEqual(self.validate(f), [])

    def test_default_path_is_network_free(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            _fixture(Path(d))
            analyzer = self.dep.DependencyAnalyzer()  # no advisory source
            analyzer.analyze(d, _cfg(False))
            self.assertEqual(analyzer.last_enrichment_status, "skipped:disabled")
            # even if networking is allowed, with no configured source it stays offline
            analyzer.analyze(d, _cfg(True))
            self.assertEqual(analyzer.last_enrichment_status, "skipped:no-source")

    def test_opt_in_enrichment_adds_advisory_findings(self) -> None:
        def source(name, spec):
            return [{"id": "CVE-2024-9999", "severity": "high"}] if name == "flask" else []

        with tempfile.TemporaryDirectory() as d:
            _fixture(Path(d))
            analyzer = self.dep.DependencyAnalyzer(advisory_source=source)
            findings = analyzer.analyze(d, _cfg(True))

        self.assertEqual(analyzer.last_enrichment_status, "ran")
        cve = [f for f in findings if "CVE-2024-9999" in f.rationale]
        self.assertEqual(len(cve), 1)
        self.assertEqual(cve[0].severity, "P1")            # high -> P1
        self.assertIn("Network-enriched", cve[0].rationale)  # provenance
        self.assertEqual(self.validate(cve[0]), [])

    def test_fail_closed_when_source_errors(self) -> None:
        def broken(name, spec):
            raise RuntimeError("advisory source unreachable")

        with tempfile.TemporaryDirectory() as d:
            _fixture(Path(d))
            analyzer = self.dep.DependencyAnalyzer(advisory_source=broken)
            findings = analyzer.analyze(d, _cfg(True))  # networking enabled but source fails

        self.assertTrue(analyzer.last_enrichment_status.startswith("skipped:error"))
        # offline findings still present; audit did not crash
        self.assertTrue(any(f.category == "dependency" for f in findings))

    def test_conforms_offline_and_deterministic(self) -> None:
        analyzer = self.dep.DependencyAnalyzer()
        self.assertIsInstance(analyzer, sys.modules["qb_analyzer_interface"].Analyzer)
        self.assertTrue(analyzer.descriptor.offline)
        with tempfile.TemporaryDirectory() as d:
            _fixture(Path(d))
            a = [f.id for f in analyzer.analyze(d, _cfg(False))]
            b = [f.id for f in analyzer.analyze(d, _cfg(False))]
            self.assertEqual(a, b)

    def test_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            _fixture(Path(d))
            before = {p.name: p.stat().st_mtime_ns for p in Path(d).iterdir()}
            self.dep.DependencyAnalyzer().analyze(d, _cfg(False))
            after = {p.name: p.stat().st_mtime_ns for p in Path(d).iterdir()}
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
