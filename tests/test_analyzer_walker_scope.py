"""AnalyzerConfig.include/exclude are honored by the default file walker.

Resolves council S7: the include/exclude fields were exposed on AnalyzerConfig but
never applied by iter_repo_files (dead config / contract drift). These tests pin
that the defaults still walk everything (byte-for-byte prior behavior) and that a
non-default include/exclude actually scopes the walk -- including end-to-end
through an analyzer's analyze().
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

CORE_PATH = SHARED_DIR / "scripts/analyzer_core.py"
IFACE_PATH = SHARED_DIR / "scripts/analyzer_interface.py"


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class WalkerScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        if not CORE_PATH.exists():
            self.skipTest("analyzer_core missing")
        self.core = _load("qb_analyzer_core_scope", CORE_PATH)
        self.iface = _load("qb_analyzer_interface_scope", IFACE_PATH)

    def _repo(self, d):
        root = Path(d)
        (root / "keep.py").write_text("x = 1\n", encoding="utf-8")
        (root / "doc.md").write_text("# doc\n", encoding="utf-8")
        return root

    def test_default_walks_everything(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = self._repo(d)
            names = {p.name for p in self.core.iter_repo_files(root)}
            self.assertIn("keep.py", names)
            self.assertIn("doc.md", names)

    def test_exclude_glob_skips_matches(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = self._repo(d)
            cfg = self.iface.AnalyzerConfig(exclude=("*.md",))
            names = {p.name for p in self.core.iter_repo_files(root, cfg)}
            self.assertIn("keep.py", names)
            self.assertNotIn("doc.md", names)

    def test_include_glob_restricts_to_matches(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = self._repo(d)
            cfg = self.iface.AnalyzerConfig(include=("*.py",))
            names = {p.name for p in self.core.iter_repo_files(root, cfg)}
            self.assertEqual(names, {"keep.py"})

    def test_analyzer_honors_exclude_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            secret = "ghp_" + "A" * 30
            (root / "leak.md").write_text(f"token {secret}\n", encoding="utf-8")
            analyzer = self.core.SecretHygieneAnalyzer()
            unscoped = analyzer.analyze(str(root), self.iface.AnalyzerConfig())
            scoped = analyzer.analyze(str(root), self.iface.AnalyzerConfig(exclude=("*.md",)))
            self.assertTrue(unscoped, "secret in leak.md should be found by default")
            self.assertEqual(scoped, [], "excluding *.md should drop the leak.md finding")


if __name__ == "__main__":
    unittest.main()
