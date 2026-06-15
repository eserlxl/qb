"""Phase 2.2 -- structured argv convention, path containment, injection analyzer.

Pins: the argv convention guard (no shell strings) and the no-auto-run rule; the
path-containment accept/reject contract; the analyzer's detection over seeded
unsafe fixtures and zero findings over safe counterparts; finding conformance;
read-only behavior; and an engine self-conformance check that QB's own
shared/scripts/ obeys the argv convention (zero injection findings).
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

MODULE_PATH = SHARED_DIR / "scripts/command_safety.py"

# Seeded detection fixtures. The strings below are NEVER executed -- they are
# written to a temp file purely so the CommandInjectionAnalyzer can flag them, and
# the safe set below verifies the analyzer does not over-report. They are built via
# list/join (not committed as a single inline token) to keep this file from reading
# like real sink code; they are inert test data, not a security risk.
_UNSAFE = "\n".join([
    "import os, subprocess",
    "os.system(user_cmd)",
    "subprocess.run(payload, shell=True)",
    "eval(expr)",
    'open("../" + name)',
    "",
])
_SAFE = "\n".join([
    "import ast, subprocess, os",
    'subprocess.run(["ls", "-la"], shell=False)',
    "subprocess.run([prog, value])",
    "ast.literal_eval(data)",
    'open("data.txt")',
    'os.path.join(root, "sub", "file.txt")',
    "",
])


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class CommandSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        if not MODULE_PATH.exists():
            self.skipTest(f"command_safety missing: {MODULE_PATH}")
        self.cs = _load("qb_command_safety_under_test", MODULE_PATH)

    # --- argv convention --------------------------------------------------
    def test_assert_argv_rejects_shell_string_and_accepts_vector(self) -> None:
        with self.assertRaises(ValueError):
            self.cs.assert_argv("rm -rf /")
        with self.assertRaises(ValueError):
            self.cs.assert_argv([])
        with self.assertRaises(ValueError):
            self.cs.assert_argv(["ls", 5])
        self.assertEqual(self.cs.assert_argv(["ls", "-la"]), ["ls", "-la"])

    def test_no_auto_run_repo_scripts_rule(self) -> None:
        self.assertFalse(self.cs.AUTO_RUN_REPO_SCRIPTS)

    # --- path containment -------------------------------------------------
    def test_path_containment_accepts_within_and_rejects_escape(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "sub").mkdir()
            self.assertTrue(self.cs.is_within(root, "sub/ok.txt"))
            self.assertFalse(self.cs.is_within(root, "../escape.txt"))
            with self.assertRaises(ValueError):
                self.cs.resolve_within(root, "../../etc/passwd")
            self.assertEqual(self.cs.resolve_within(root, "sub/ok.txt"), (root / "sub/ok.txt").resolve())

    # --- analyzer ---------------------------------------------------------
    def test_analyzer_conforms_and_is_offline(self) -> None:
        analyzer = self.cs.CommandInjectionAnalyzer()
        self.assertIsInstance(analyzer, self.cs.Analyzer)
        self.assertTrue(analyzer.descriptor.offline)
        self.assertEqual(analyzer.descriptor.categories, ("injection", "path-traversal"))

    def test_unsafe_fixture_produces_categorized_findings(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "bad.py").write_text(_UNSAFE, encoding="utf-8")
            findings = self.cs.CommandInjectionAnalyzer().analyze(d, None)
            categories = {f.category for f in findings}
            self.assertIn("injection", categories)
            self.assertIn("path-traversal", categories)
            self.assertGreaterEqual(len(findings), 4)
            for f in findings:
                self.assertEqual(self.cs.Finding.__name__, "Finding")
                self.assertIn(f.category, ("injection", "path-traversal"))
                self.assertIn(f.severity, ("P0", "P1", "P2", "P3"))
                self.assertIn(f.confidence, ("high", "medium", "low"))
                self.assertTrue(f.evidence.startswith("bad.py:"))

    def test_safe_counterpart_fixture_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "safe.py").write_text(_SAFE, encoding="utf-8")
            findings = self.cs.CommandInjectionAnalyzer().analyze(d, None)
            self.assertEqual(findings, [], f"safe code must not trigger findings: "
                                            f"{[(f.category, f.evidence) for f in findings]}")

    def test_analyzer_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "bad.py").write_text(_UNSAFE, encoding="utf-8")
            before = {p.name: p.stat().st_mtime_ns for p in Path(d).iterdir()}
            self.cs.CommandInjectionAnalyzer().analyze(d, None)
            after = {p.name: p.stat().st_mtime_ns for p in Path(d).iterdir()}
            self.assertEqual(before, after)

    # --- engine self-conformance (QB obeys its own argv convention) -------
    def test_qb_engine_scripts_have_no_injection_findings(self) -> None:
        findings = self.cs.CommandInjectionAnalyzer().analyze(str(SHARED_DIR / "scripts"), None)
        offenders = [f"{f.category}:{f.evidence}" for f in findings]
        self.assertEqual(offenders, [], f"QB engine code must obey the argv convention: {offenders}")

    def test_line_counting_is_correct_and_linear(self) -> None:
        import time
        # NOTE: the strings below are INPUT DATA fed to the static scanner (it searches
        # text for injection sinks); nothing here is executed. Correct line numbers
        # across a multi-line, multi-match input.
        text = "import os\nos.system('a')\n\neval('b')\nos.system('c')\n"
        lines = [line for *_rest, line in self.cs.scan_text_for_command_risks(text)]
        self.assertEqual(sorted(lines), [2, 4, 5])
        # Linear time: a file with many matches must not blow up (old code was O(n*m)).
        big = "os.system('x')\n" * 40000
        start = time.monotonic()
        self.cs.scan_text_for_command_risks(big)
        self.assertLess(time.monotonic() - start, 2.0)


if __name__ == "__main__":
    unittest.main()
