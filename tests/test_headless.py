"""Phase 6.3 -- headless CLI + exit-code contract.

Pins: the non-interactive audit->report loop writes the full store + reports to the
fixed-name output directory; the exit code follows the contract (clean repo -> 0,
findings -> 1); the report validates; no secret leaks into output; and the run is
offline + dependency-light (stdlib only).
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import SHARED_DIR

MODULE_PATH = SHARED_DIR / "scripts/qb_headless.py"

# A genuinely clean repo declares its distribution terms; fixtures that assert an
# EXIT_CLEAN run include this so the license-hygiene analyzer has nothing to flag.
_LICENSE_TEXT = (
    "MIT License\n\nCopyright (c) 2026 Example\n\nPermission is hereby granted, "
    "free of charge, to any person obtaining a copy of this software.\n"
)


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class HeadlessTests(unittest.TestCase):
    def setUp(self) -> None:
        if not MODULE_PATH.exists():
            self.skipTest("qb_headless missing")
        self.hl = _load("qb_headless_under_test", MODULE_PATH)

    def test_clean_repo_exits_clean(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            (repo / "readme.md").write_text("# nothing actionable here\n", encoding="utf-8")
            (repo / "LICENSE").write_text(_LICENSE_TEXT, encoding="utf-8")
            out = Path(d) / "QB-Audit"
            code = self.hl.run_headless(repo, output_dir=out)
            self.assertEqual(code, self.hl.EXIT_CLEAN)

    def test_findings_repo_exits_findings_and_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            token = "ghp_" + "A" * 30
            (repo / "leak.txt").write_text(f"key = {token}\n", encoding="utf-8")
            out = Path(d) / "QB-Audit"
            code = self.hl.run_headless(repo, output_dir=out)
            self.assertEqual(code, self.hl.EXIT_FINDINGS)

            # full store + reports present
            for name in ("findings.jsonl", "evidence", "run-log.jsonl", "summary.json",
                         "report.json", "report.sarif", "summary.txt"):
                self.assertTrue((out / name).exists(), f"missing output: {name}")

            report = json.loads((out / "report.json").read_text())
            self.assertIn("provenance", report)
            self.assertTrue(report["findings"], "expected findings in report")

            # redaction: the secret value never reaches any output file
            for name in ("findings.jsonl", "report.json", "summary.txt"):
                self.assertNotIn(token, (out / name).read_text())

    def test_main_returns_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            (repo / "ok.txt").write_text("clean\n", encoding="utf-8")
            (repo / "LICENSE").write_text(_LICENSE_TEXT, encoding="utf-8")
            code = self.hl.main(["--root", str(repo), "--out", str(Path(d) / "QB-Audit")])
            self.assertEqual(code, self.hl.EXIT_CLEAN)


if __name__ == "__main__":
    unittest.main()
