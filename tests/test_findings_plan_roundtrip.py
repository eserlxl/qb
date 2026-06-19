"""Phase 6.3 -- findings -> plan round-trip (end to end).

Loads the committed findings fixture, projects it with the findings_to_plan
projector, and asserts the assembled planwright plan is lint-clean
(validate_plan returns zero errors) and carries no committed secret (the same
analyzer_core secret scan the validator runs under --strict). This exercises the
full findings.jsonl -> read -> project -> validate path -- the load path the
per-category conformance test (test_findings_to_plan) does not cover -- and confirms
the planning-state finding is dropped, not projected.
"""

from __future__ import annotations

import contextlib
import io
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from tests.qb_monorepo import REPO_ROOT, SHARED_DIR

FIXTURE = REPO_ROOT / "tests/fixtures/findings_roundtrip.jsonl"
# The fixture's non-planning-state evidence paths, created so Surfaces exist and
# repair anchors resolve. The sixth fixture finding is .qb/-anchored (skipped).
FIXTURE_FILES = ("config/sample.env", "src/app.py", "src/util.py",
                 "requirements.txt", "LICENSE")


def _load(name: str, filename: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SHARED_DIR / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


fs = _load("qb_finding_schema", "finding_schema.py")
ftp = _load("qb_findings_to_plan", "findings_to_plan.py")
vpp = _load("qb_validate_planwright_plan", "validate_planwright_plan.py")
core = _load("qb_analyzer_core", "analyzer_core.py")


class FindingsPlanRoundTripTest(unittest.TestCase):
    def _materialize(self, root: Path):
        for rel in FIXTURE_FILES:
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("\n".join(f"line {i}" for i in range(1, 21)), encoding="utf-8")

    def test_fixture_findings_project_to_a_lint_clean_plan(self):
        findings = [fs.Finding.from_dict(json.loads(ln))
                    for ln in FIXTURE.read_text(encoding="utf-8").splitlines() if ln.strip()]
        self.assertGreaterEqual(len(findings), 6)

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._materialize(root)
            skipped = []
            text = ftp.project_findings(findings, str(root), skipped=skipped)

            # Every non-planning-state finding projects; the .qb/-anchored one is skipped.
            self.assertEqual(text.count("- [ ]"), len(FIXTURE_FILES))
            self.assertEqual(len(skipped), 1)
            self.assertTrue(any(".qb/" in reason for _f, reason in skipped))

            errors, _advisories, count = vpp.validate_plan(text, str(root))
            self.assertEqual(errors, [], errors)
            self.assertEqual(count, len(FIXTURE_FILES))

            # The same secret scan the validator runs under --strict: zero findings.
            self.assertEqual(core.scan_text_for_secrets(text), [])

            audit = root / ".qb/audit"
            audit.mkdir(parents=True)
            (audit / "findings.jsonl").write_text(FIXTURE.read_text(encoding="utf-8"),
                                                  encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = ftp.main(["--root", str(root)])
            out = buf.getvalue()
            self.assertEqual(code, 0, out)
            self.assertIn("planwright_plan_validation=passed", out)
            self.assertIn("findings_projected=5", out)
            self.assertIn("findings_skipped=1", out)
            self.assertFalse((root / ".qb/plan.md").exists())
            self.assertFalse((root / ".planwright").exists())


if __name__ == "__main__":
    unittest.main()
