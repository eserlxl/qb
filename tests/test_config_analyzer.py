"""Net-new config-hygiene analyzer.

Completes the last wired-but-unproduced ``config`` finding category (it is in the
frozen schema and bound to the fixer's ``config-review`` recipe, but only a no-op
reference analyzer declared it). Pins: committed-dotenv detection, template-file
exemption, a clean no-finding case, schema conformance, read-only behavior, and
registration in the default audit registry.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

CONFIG_PATH = SHARED_DIR / "scripts/analyzer_config.py"
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


class ConfigAnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        if not CONFIG_PATH.exists():
            self.skipTest("analyzer_config not built yet")
        self.mod = _load("qb_analyzer_config_under_test", CONFIG_PATH)
        self.ai = _load("qb_analyzer_interface", INTERFACE_PATH)
        self.cfg = self.ai.AnalyzerConfig()

    def _analyze(self, files: dict) -> list:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name, content in files.items():
                (root / name).write_text(content, encoding="utf-8")
            return self.mod.ConfigHygieneAnalyzer().analyze(str(root), self.cfg)

    def test_committed_dotenv_is_flagged(self) -> None:
        findings = self._analyze({".env": "API_KEY=abc\n", "README.md": "# p\n"})
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, "config")
        self.assertEqual(findings[0].fix_strategy, "manual")
        self.assertEqual(findings[0].evidence, ".env:1")
        self.assertEqual(self.ai.validate_finding(findings[0]), [])

    def test_named_dotenv_is_flagged(self) -> None:
        findings = self._analyze({".env.production": "DB=prod\n"})
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].evidence, ".env.production:1")

    def test_template_dotenv_is_not_flagged(self) -> None:
        self.assertEqual(self._analyze({".env.example": "API_KEY=\n"}), [])
        self.assertEqual(self._analyze({".env.sample": "API_KEY=\n"}), [])
        self.assertEqual(self._analyze({".env.template": "API_KEY=\n"}), [])

    def test_clean_repo_yields_nothing(self) -> None:
        self.assertEqual(self._analyze({"README.md": "# p\n", "config.json": "{}\n"}), [])

    def test_descriptor_and_default_registration(self) -> None:
        descriptor = self.mod.ConfigHygieneAnalyzer().descriptor
        self.assertEqual(descriptor.id, "config-hygiene")
        self.assertEqual(descriptor.categories, ("config",))
        self.assertTrue(descriptor.offline)
        runner = _load("qb_audit_runner_config_test", RUNNER_PATH)
        ids = {a.descriptor.id for a in runner.build_default_registry().analyzers()}
        self.assertIn("config-hygiene", ids)

    def test_analyzer_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".env").write_text("X=1\n", encoding="utf-8")
            before = sorted(p.name for p in root.iterdir())
            self.mod.ConfigHygieneAnalyzer().analyze(str(root), self.cfg)
            self.assertEqual(before, sorted(p.name for p in root.iterdir()))


if __name__ == "__main__":
    unittest.main()
