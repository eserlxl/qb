"""Phase 2.4 -- dependency & supply-chain analyzer (offline default, opt-in net).

Pins: the offline tier (unpinned dependency + missing-lockfile hygiene findings,
pinned deps clean); the default network-free path (enrichment skipped); opt-in
enrichment with a configured source (CVE evidence + provenance + severity);
fail-closed fallback when the source errors; conformance; determinism; read-only.
No real network is used -- the advisory source is an injected callable.
"""

from __future__ import annotations

import importlib.util
import json
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

    def test_vcs_url_requirements_are_skipped_not_misparsed(self) -> None:
        # Resolves council S12: a git+https / bare-URL requirement must not be
        # split into a bogus "git" dependency, and carries no PyPI version to pin.
        body = (
            "git+https://github.com/psf/requests.git#egg=requests\n"
            "https://example.com/pkg-1.0.whl\n"
            "flask\n"
            "django==4.2.1\n"
        )
        deps = self.dep.parse_requirements(body)
        names = [d["name"] for d in deps]
        self.assertNotIn("git", names)
        self.assertEqual(names, ["flask", "django"])  # only the real PyPI deps
        self.assertFalse(next(d for d in deps if d["name"] == "flask")["pinned"])
        self.assertTrue(next(d for d in deps if d["name"] == "django")["pinned"])

    def test_npm_nonregistry_specs_are_skipped_not_flagged_unpinned(self) -> None:
        # A git/github/file/link/workspace/url npm dependency carries no registry
        # version to pin, so it must not be reported "unpinned" (the npm twin of the
        # pip VCS/URL skip). A registry range like ^1.0.0 is still flagged.
        body = json.dumps({"dependencies": {
            "express": "^1.0.0",
            "pinned": "1.2.3",
            "gitdep": "git+https://github.com/u/r.git",
            "ghdep": "github:u/r",
            "filedep": "file:../local",
            "linkdep": "link:../l",
            "workdep": "workspace:*",
        }})
        names = {d["name"] for d in self.dep.parse_package_json(body)}
        self.assertEqual(names, {"express", "pinned"})  # only the registry deps
        deps = {d["name"]: d for d in self.dep.parse_package_json(body)}
        self.assertFalse(deps["express"]["pinned"])  # ^1.0.0 still flagged unpinned
        self.assertTrue(deps["pinned"]["pinned"])

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

    def test_cargo_workspace_and_target_tables_are_scanned(self) -> None:
        # A supply-chain audit must not stop at top-level [dependencies]: unpinned
        # deps under [workspace.dependencies] and [target.<cfg>.dependencies] are
        # equally a hygiene gap. Pinned (=X.Y.Z) and git/path entries stay clean.
        body = (
            '[workspace.dependencies]\n'
            'serde = "1.0"\n'                       # caret -> unpinned
            'tokio = "=1.35.0"\n'                   # exact -> clean
            'localdep = {path = "../localdep"}\n'   # path -> no version, skipped
            "[target.'cfg(unix)'.dependencies]\n"
            'libc = "0.2"\n'                        # caret -> unpinned
        )
        deps = {d["name"]: d for d in self.dep.parse_cargo(body)}
        self.assertIn("serde", deps)
        self.assertFalse(deps["serde"]["pinned"])
        self.assertEqual(deps["serde"]["section"], "workspace.dependencies")
        self.assertIn("tokio", deps)
        self.assertTrue(deps["tokio"]["pinned"])      # exact pin is clean
        self.assertNotIn("localdep", deps)            # path dep skipped
        self.assertIn("libc", deps)
        self.assertFalse(deps["libc"]["pinned"])
        self.assertEqual(deps["libc"]["section"], "target(cfg(unix)).dependencies")

    def test_cargo_toml_without_lockfile_is_flagged(self) -> None:
        # Cargo.toml present but no Cargo.lock -> reproducibility hygiene finding,
        # mirroring the existing package.json missing-lockfile rule.
        expected_id = self.dep.compute_finding_id(
            "dependency", "Cargo.toml:1", "missing-cargo-lockfile")
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            root.joinpath("Cargo.toml").write_text(
                '[package]\nname = "x"\nversion = "0.1.0"\n', encoding="utf-8")
            findings = self.dep.DependencyAnalyzer().analyze(d, _cfg(False))
        match = [f for f in findings if f.id == expected_id]
        self.assertEqual(len(match), 1, "expected exactly one missing-cargo-lockfile finding")
        self.assertEqual(match[0].category, "dependency")
        self.assertEqual(match[0].evidence, "Cargo.toml:1")
        self.assertEqual(self.validate(match[0]), [])

    def test_cargo_lock_present_suppresses_missing_lockfile(self) -> None:
        expected_id = self.dep.compute_finding_id(
            "dependency", "Cargo.toml:1", "missing-cargo-lockfile")
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            root.joinpath("Cargo.toml").write_text(
                '[package]\nname = "x"\nversion = "0.1.0"\n', encoding="utf-8")
            root.joinpath("Cargo.lock").write_text("# lockfile\n", encoding="utf-8")
            findings = self.dep.DependencyAnalyzer().analyze(d, _cfg(False))
        self.assertFalse(
            any(f.id == expected_id for f in findings),
            "Cargo.lock present must suppress the missing-cargo-lockfile finding",
        )

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

    def test_poetry_git_path_dependencies_are_skipped(self) -> None:
        # A poetry git/path dep (inline table without a version) carries no
        # registry version to pin and must not be flagged "unpinned"; a poetry
        # dep that DOES carry a version is still parsed (and pin-checked).
        body = (
            '[tool.poetry.dependencies]\n'
            'python = "^3.11"\n'
            'mylib = {git = "https://github.com/u/r.git"}\n'
            'localdep = {path = "../localdep"}\n'
            'requests = {version = "^2.31"}\n'
            'pinned = {version = "2.2.1"}\n'
        )
        names = [d["name"] for d in self.dep.parse_pyproject(body)]
        self.assertNotIn("mylib", names)     # git dep skipped
        self.assertNotIn("localdep", names)  # path dep skipped
        self.assertIn("requests", names)     # versioned dict dep kept
        self.assertIn("pinned", names)
        by_name = {d["name"]: d for d in self.dep.parse_pyproject(body)}
        self.assertFalse(by_name["requests"]["pinned"])  # ^2.31 is a range
        self.assertTrue(by_name["pinned"]["pinned"])     # 2.2.1 is exact

    def test_pyproject_non_table_project_or_tool_does_not_crash(self) -> None:
        # A TOML-valid pyproject that declares `project` or `tool` as a scalar
        # must fail closed to [] rather than raise AttributeError out of the
        # offline tier. The whole repo body is untrusted input.
        for body in ('project = "foo"\n', 'tool = "x"\n', 'project = 7\ntool = []\n'):
            self.assertEqual(self.dep.parse_pyproject(body), [], msg=f"body={body!r}")

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
