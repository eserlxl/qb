"""Breadth analyzer tests."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

BREADTH_PATH = SHARED_DIR / "scripts/analyzer_breadth.py"
INTERFACE_PATH = SHARED_DIR / "scripts/analyzer_interface.py"
RUNNER_PATH = SHARED_DIR / "scripts/audit_runner.py"


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class BreadthAnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        if not BREADTH_PATH.exists():
            self.skipTest("analyzer_breadth not built yet")
        self.mod = _load("qb_analyzer_breadth_under_test", BREADTH_PATH)
        self.ai = _load("qb_analyzer_interface", INTERFACE_PATH)
        self.cfg = self.ai.AnalyzerConfig()

    def _analyze(self, files: dict) -> list:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name, content in files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            return self.mod.WorkflowActionAnalyzer().analyze(str(root), self.cfg)

    def test_broad_github_action_ref_is_flagged(self) -> None:
        findings = self._analyze({
            ".github/workflows/ci.yml": (
                "name: ci\n"
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - uses: actions/checkout@v4\n"
                "      - uses: docker/login-action@main\n"
                "      - uses: owner/action\n"
            )
        })
        self.assertEqual(len(findings), 3)
        self.assertEqual(
            [f.evidence for f in findings],
            [
                ".github/workflows/ci.yml:5",
                ".github/workflows/ci.yml:6",
                ".github/workflows/ci.yml:7",
            ],
        )
        for finding in findings:
            self.assertEqual(finding.category, "dependency")
            self.assertEqual(finding.fix_strategy, "manual")
            self.assertEqual(self.ai.validate_finding(finding), [])

    def test_write_all_permissions_is_flagged(self) -> None:
        findings = self._analyze({
            ".github/workflows/ci.yml": (
                "name: ci\n"
                "permissions: write-all\n"
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - uses: actions/checkout@v4.2.2\n"
            )
        })
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.evidence, ".github/workflows/ci.yml:2")
        self.assertEqual(finding.category, "dependency")
        self.assertEqual(finding.severity, "P2")
        self.assertIn("write-all", finding.rationale)
        self.assertEqual(self.ai.validate_finding(finding), [])

    def test_scoped_permissions_are_clean(self) -> None:
        # The narrow, intended grant (contents: read) must not be flagged.
        self.assertEqual(
            self._analyze({
                ".github/workflows/ci.yml": (
                    "name: ci\n"
                    "permissions:\n"
                    "  contents: read\n"
                    "jobs:\n"
                    "  t:\n"
                    "    steps:\n"
                    "      - uses: actions/checkout@v4.2.2\n"
                )
            }),
            [],
        )

    def test_full_semver_and_sha_refs_are_clean(self) -> None:
        findings = self._analyze({
            ".github/workflows/ci.yml": (
                "name: ci\n"
                "jobs:\n"
                "  test:\n"
                "    steps:\n"
                "      - uses: actions/checkout@v4.2.2\n"
                "      - uses: actions/setup-python@8f4aaab067a4fc6aecf9d2dcd3b82b6bfbdb7902\n"
            )
        })
        self.assertEqual(findings, [])

    def test_local_actions_and_non_workflow_files_are_clean(self) -> None:
        self.assertEqual(
            self._analyze({
                ".github/workflows/ci.yml": "jobs:\n  t:\n    steps:\n      - uses: ./local-action\n",
                "README.md": "- uses: owner/action@main\n",
            }),
            [],
        )

    def test_descriptor_and_default_registration(self) -> None:
        descriptor = self.mod.WorkflowActionAnalyzer().descriptor
        self.assertEqual(descriptor.id, "workflow-actions")
        self.assertEqual(descriptor.categories, ("dependency",))
        self.assertTrue(descriptor.offline)
        runner = _load("qb_audit_runner_breadth_test", RUNNER_PATH)
        ids = {a.descriptor.id for a in runner.build_default_registry().analyzers()}
        self.assertIn("workflow-actions", ids)

    def test_analyzer_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            workflow = root / ".github/workflows/ci.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text("jobs:\n  t:\n    steps:\n      - uses: actions/checkout@v4\n", encoding="utf-8")
            before = sorted(p.as_posix() for p in root.rglob("*"))
            self.mod.WorkflowActionAnalyzer().analyze(str(root), self.cfg)
            after = sorted(p.as_posix() for p in root.rglob("*"))
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
