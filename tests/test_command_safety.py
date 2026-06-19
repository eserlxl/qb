"""Phase 2.2 -- structured argv convention, path containment, injection analyzer.

Pins: the argv convention guard (no shell strings) and the no-auto-run rule; the
path-containment accept/reject contract; the analyzer's detection over seeded
unsafe fixtures and zero findings over safe counterparts; finding conformance;
read-only behavior; and an engine self-conformance check that QB's own
shared/scripts/ obeys the argv convention (zero injection findings).
"""

from __future__ import annotations

import importlib.util
import os
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

    def test_minimal_env_forwards_only_allowlist_and_keeps_path(self) -> None:
        # A credential in QB's own environment must never reach a repo-provided
        # command: minimal_env forwards only the allowlisted keys (PATH/HOME/
        # locale/...) and drops everything else, including any injected token.
        # Values here are plainly synthetic, not real secrets.
        base = {
            "PATH": "/custom/bin",
            "HOME": "/home/qb",
            "LC_ALL": "C",
            "QB_INJECTED_KEY": "inert-non-secret-test-value",
        }
        env = self.cs.minimal_env(base)
        self.assertEqual(env["PATH"], "/custom/bin", "PATH must be preserved")
        self.assertEqual(env.get("HOME"), "/home/qb", "allowlisted HOME must survive")
        self.assertEqual(env.get("LC_ALL"), "C", "LC_ prefix must be allowlisted")
        self.assertNotIn(
            "QB_INJECTED_KEY", env,
            "a non-allowlisted environment key must be dropped before reaching a command",
        )

    def test_minimal_env_falls_back_path_to_defpath(self) -> None:
        # With no PATH in the base env, minimal_env must still provide one so the
        # command remains locatable -- the documented os.defpath fallback.
        env = self.cs.minimal_env({"HOME": "/home/qb"})
        self.assertEqual(env["PATH"], os.defpath)

    # --- confine-by-default -----------------------------------------------
    def test_run_command_confines_by_default_when_available(self) -> None:
        # On a host with the required control, an unspecified run_command confines
        # by default (no caller has to opt in to the safe path).
        if "process_group" not in self.cs.available_confinement_controls():
            self.skipTest("process confinement unavailable on this host")
        completed = self.cs.run_command([sys.executable, "-c", ""])
        self.assertTrue(completed.qb_confinement["enabled"])
        self.assertIn("process_group", completed.qb_confinement["controls"])
        self.assertIsNone(completed.qb_confinement["opt_out_reason"])
        self.assertEqual(completed.returncode, 0)

    def test_run_command_fails_closed_when_required_control_missing(self) -> None:
        # Simulate a host lacking the required process_group control: the default
        # confinement must refuse to run (ConfinementUnavailable) BEFORE any child
        # spawns, never silently fall back to an unconfined run.
        original = self.cs.available_confinement_controls
        self.cs.available_confinement_controls = lambda: ()
        try:
            with tempfile.TemporaryDirectory() as d:
                marker = Path(d) / "spawned.txt"
                cmd = [
                    sys.executable,
                    "-c",
                    f"import pathlib; pathlib.Path({str(marker)!r}).write_text('spawned')",
                ]
                with self.assertRaises(self.cs.ConfinementUnavailable):
                    self.cs.run_command(cmd)
                self.assertFalse(
                    marker.exists(),
                    "missing required controls must fail before spawn",
                )
        finally:
            self.cs.available_confinement_controls = original

    def test_run_command_fails_closed_when_required_control_unsupported(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            marker = Path(d) / "spawned.txt"
            cmd = [
                sys.executable,
                "-c",
                f"import pathlib; pathlib.Path({str(marker)!r}).write_text('spawned')",
            ]
            with self.assertRaises(self.cs.ConfinementUnavailable) as cm:
                self.cs.run_command(
                    cmd,
                    confinement={"require": ("process_group", "filesystem_namespace")},
                )
            self.assertFalse(
                marker.exists(),
                "unsupported required controls must fail before spawn",
            )
        self.assertIn("unsupported confinement control", str(cm.exception))

    def test_explicit_unconfined_opt_out_runs_uncontained_with_reason(self) -> None:
        with self.assertRaises(ValueError):
            self.cs.unconfined(" ")
        completed = self.cs.run_command(
            [sys.executable, "-c", ""],
            confinement=self.cs.unconfined("trusted internal command"),
        )
        self.assertFalse(completed.qb_confinement["enabled"])
        self.assertEqual(completed.qb_confinement["controls"], ())
        self.assertEqual(completed.qb_confinement["opt_out_reason"], "trusted internal command")
        self.assertEqual(completed.returncode, 0)
        shorthand = self.cs.run_command([sys.executable, "-c", ""], confinement=False)
        self.assertFalse(shorthand.qb_confinement["enabled"])
        self.assertEqual(shorthand.qb_confinement["controls"], ())
        self.assertEqual(shorthand.qb_confinement["opt_out_reason"], "explicit unconfined opt-out")

    def test_true_and_explicit_spec_confine_like_default(self) -> None:
        # confinement=True and an explicit default ConfinementSpec must behave
        # identically to the unspecified default: confine before spawn and attach
        # the qb_confinement record on a supported host (no input variant is a
        # silent unconfined fallback).
        if "process_group" not in self.cs.available_confinement_controls():
            self.skipTest("process confinement unavailable on this host")
        for confinement in (True, self.cs.ConfinementSpec()):
            completed = self.cs.run_command(
                [sys.executable, "-c", ""], confinement=confinement
            )
            self.assertTrue(
                completed.qb_confinement["enabled"],
                f"confinement={confinement!r} must confine before spawn",
            )
            self.assertIn("process_group", completed.qb_confinement["controls"])
            self.assertIsNone(completed.qb_confinement["opt_out_reason"])
            self.assertEqual(completed.returncode, 0)

    def test_default_confinement_establishes_all_available_controls(self) -> None:
        # The default spec is best-effort beyond the required floor: every available
        # supported control (process_group AND resource_limits when present) is
        # established, not only the required process_group.
        available = self.cs.available_confinement_controls()
        if "process_group" not in available:
            self.skipTest("process confinement unavailable on this host")
        completed = self.cs.run_command([sys.executable, "-c", ""])
        for control in available:
            self.assertIn(control, completed.qb_confinement["controls"])

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
            # An absolute out-of-repo path escapes the root and is refused.
            with self.assertRaises(ValueError):
                self.cs.resolve_within(root, "/etc/passwd")
            self.assertFalse(self.cs.is_within(root, "/etc/passwd"))
            # A symlink whose target is outside the root is resolved (symlinks
            # followed) and refused -- a fix cannot escape isolation via a link.
            with tempfile.TemporaryDirectory() as outside_d:
                (root / "link").symlink_to(outside_d)
                with self.assertRaises(ValueError):
                    self.cs.resolve_within(root, "link/secret.txt")
                self.assertFalse(self.cs.is_within(root, "link/secret.txt"))

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

    def test_qb_ignore_suppresses_and_records_reason(self) -> None:
        text = "\n".join([
            "import os",
            "# qb-ignore: system-shell-call fixture exercises a documented false-positive control",
            "os.system(cmd)",
            "",
        ])
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "suppressed.py").write_text(text, encoding="utf-8")
            analyzer = self.cs.CommandInjectionAnalyzer()
            findings = analyzer.analyze(d, None)
        self.assertEqual(findings, [])
        self.assertEqual(analyzer.last_suppression_report, [{
            "rule": "system-shell-call",
            "evidence": "suppressed.py:3",
            "reason": "fixture exercises a documented false-positive control",
        }])

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
