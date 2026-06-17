"""Phase 5.4 -- cross-host planner-validator smoke.

Runs each of the four hosts' BUNDLED ``validate_planner_docs.py`` against a synthetic
``.qb`` fixture built to that host's own heading contract, asserting it passes on a
valid tree and fails closed on an incomplete one. This exercises each *shipped*
validator end-to-end (a launch proof), not merely that the file exists.

Why per-host fixtures: the validators diverge in heading text (e.g. shared
"Architectural Direction" vs antigravity "Architecture Direction"; "Prioritized
Elaboration Order" vs "Priority Detailing Order"), so each fixture is built from the
host validator's own ``*_HEADINGS`` constants. This is the only end-to-end smoke of
Antigravity's divergent, non-synced validator; for the three engine hosts it also
proves each shipped copy launches directly, independent of the sync-identity argument
that ``test_validator_refactor_nonregression`` (which runs only the shared validator)
relies on.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.qb_monorepo import REPO_ROOT

HOST_VALIDATORS = {
    "claude-code": REPO_ROOT / "platforms/claude-code/scripts/validate_planner_docs.py",
    "cursor": REPO_ROOT / "platforms/cursor/scripts/validate_planner_docs.py",
    "codex": REPO_ROOT / "platforms/codex/plugins/qb/skills/qb/scripts/validate_planner_docs.py",
    "antigravity": REPO_ROOT / "platforms/antigravity/skills/qb/scripts/validate_planner_docs.py",
}

SUBPLAN_REF = ".qb/phase-1-plans/phase-1.1-validator-fixture.md"


def _load_validator(host: str, path: Path):
    name = f"smoke_validator_{host}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    # Register before exec so @dataclass can resolve the module via __module__.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _write_doc(path: Path, headings, bodies=None):
    bodies = bodies or {}
    lines = []
    for index, heading in enumerate(headings, start=1):
        lines += [
            heading,
            "",
            bodies.get(
                heading,
                f"Fixture content for section {index} is intentionally complete enough "
                "for the planner document validator.",
            ),
            "",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _build_valid_tree(root: Path, validator) -> None:
    """Build a .qb tree valid for this validator, parameterized by its heading
    constants so it satisfies whichever host contract is in play."""
    qb = root / ".qb"
    phase_dir = qb / "phase-1-plans"
    phase_dir.mkdir(parents=True)

    _write_doc(qb / "main-planning.md", validator.STEP1_HEADINGS, {
        validator.ROADMAP_HEADING: (
            "| Phase | Summary |\n| --- | --- |\n| 1 | Build the smoke fixture. |"),
    })

    index_headings = validator.INDEX_HEADINGS
    _write_doc(qb / "sub-planning-index.md", index_headings, {
        index_headings[3]: f"- {SUBPLAN_REF}",   # "## 3. Phase and Sub-Plan Map"
        index_headings[4]: f"1. {SUBPLAN_REF}",   # "## 4. <prioritized order>"
    })

    _write_doc(qb / "sub-planning-audit.md", validator.AUDIT_HEADINGS)

    subplan_lines = ["# Phase 1.1 - Validator Fixture", ""]
    for index, heading in enumerate(validator.SUBPLAN_HEADINGS, start=1):
        subplan_lines += [
            heading,
            "",
            f"Fixture body {index} contains enough concrete planning detail to satisfy "
            "structure and minimum-length checks.",
            "",
        ]
    (phase_dir / "phase-1.1-validator-fixture.md").write_text(
        "\n".join(subplan_lines), encoding="utf-8")


def _run(validator_path: Path, root: Path):
    return subprocess.run(
        [sys.executable, str(validator_path), "--mode", "all", "--root", str(root)],
        text=True, capture_output=True, check=False)


class CrossHostSmokeTest(unittest.TestCase):
    def test_each_host_validator_passes_valid_and_rejects_incomplete(self):
        for host, vpath in HOST_VALIDATORS.items():
            with self.subTest(host=host):
                self.assertTrue(vpath.is_file(), f"{host}: validator missing at {vpath}")
                validator = _load_validator(host, vpath)
                with TemporaryDirectory() as d:
                    root = Path(d)
                    _build_valid_tree(root, validator)

                    ok = _run(vpath, root)
                    self.assertEqual(
                        ok.returncode, 0,
                        f"{host} validator rejected a valid fixture:\n{ok.stdout}\n{ok.stderr}")

                    # Break the tree: remove the index. The validator must fail closed.
                    (root / ".qb/sub-planning-index.md").unlink()
                    bad = _run(vpath, root)
                    self.assertNotEqual(
                        bad.returncode, 0,
                        f"{host} validator passed an incomplete fixture:\n{bad.stdout}")


if __name__ == "__main__":
    unittest.main()
