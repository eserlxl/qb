"""Guard: BASELINE.md stays consistent with the live tree.

BASELINE.md is the committed gate-of-record reference, but nothing derived its
stated version or test-suite counts from the source of truth, so it silently
drifted after the tree moved forward. This guard pins it the same way
``tests/test_doc_consistency.py`` pins the README: every value BASELINE asserts
is re-derived from the live tree and compared.

Semantics:

* the stated **version** must equal the root ``VERSION`` file exactly, and
* the live module / test-case counts must equal every count BASELINE states, so
  adding or removing tests requires updating the committed baseline reference,
* the documented ``make check`` command inventory must match the Makefile
  recipe, and
* the documented baseline guard command set must match the guard mapping.

Standard library only, like the rest of the suite.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.qb_monorepo import REPO_ROOT

BASELINE = REPO_ROOT / "BASELINE.md"
VERSION_FILE = REPO_ROOT / "VERSION"
MAKEFILE = REPO_ROOT / "Makefile"
TESTS_DIR = REPO_ROOT / "tests"

_STATED_VERSION = re.compile(r"Version \(`VERSION`\)\s*\|\s*`(\d+\.\d+\.\d+)`")
# Every place BASELINE states a module count.
_MODULE_COUNTS = (
    re.compile(r"Test modules \(`tests/test_\*\.py`\)\s*\|\s*(\d+)"),
    re.compile(r"Expected test modules\s*\|\s*(\d+)"),
    re.compile(r"\((\d+) modules / \d+ functions\)"),
    re.compile(r"other than (\d+) modules"),
)
# Every place BASELINE states a function/test-case count.
_FUNCTION_COUNTS = (
    re.compile(r"^\| Test functions\s*\|\s*(\d+)", re.MULTILINE),
    re.compile(r"Expected test functions\s*\|\s*(\d+)"),
    re.compile(r"\(\d+ modules / (\d+) functions\)"),
    re.compile(r"other than \d+ modules or (\d+) passing test cases"),
)
_SECTION = r"^## {heading}\s*$(?P<body>.*?)(?=^## |\Z)"
_INVENTORY_COMMAND = re.compile(r"^\| `([^`]+)` \|", re.MULTILINE)
_GUARD_MAPPING_COMMAND = re.compile(
    r"^\| [^|]+ \| `python3 -m unittest tests\.(test_[a-z0-9_]+)` \|",
    re.MULTILINE,
)
_GUARD_SET_COMMAND = re.compile(r"tests\.(test_[a-z0-9_]+)")


def _live_modules() -> int:
    return len(list(TESTS_DIR.glob("test_*.py")))


def _live_functions() -> int:
    # Match the command BASELINE names instead of counting text. Several tests
    # carry fixture strings containing "def test_*"; discovery's count is the
    # operator-visible number.
    return unittest.TestLoader().discover(str(TESTS_DIR)).countTestCases()


def _counts(text: str, patterns) -> list[int]:
    found: list[int] = []
    for rx in patterns:
        found.extend(int(m) for m in rx.findall(text))
    return found


def _section(text: str, heading: str) -> str:
    match = re.search(
        _SECTION.format(heading=re.escape(heading)),
        text,
        re.MULTILINE | re.DOTALL,
    )
    if match is None:
        return ""
    return match.group("body")


def _make_target_commands(text: str, target: str) -> list[str]:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line == f"{target}:":
            commands: list[str] = []
            for recipe_line in lines[index + 1:]:
                if recipe_line.startswith("\t"):
                    command = recipe_line.strip()
                    if command:
                        commands.append(command)
                    continue
                if recipe_line.strip() and not recipe_line.startswith("#"):
                    break
            return commands
    return []


class BaselineConsistencyTests(unittest.TestCase):
    def setUp(self) -> None:
        for path in (BASELINE, VERSION_FILE):
            if not path.exists():
                self.skipTest(f"{path.name} missing")
        self.text = BASELINE.read_text(encoding="utf-8")
        self.live_version = VERSION_FILE.read_text(encoding="utf-8").strip()

    def test_version_matches_version_file(self) -> None:
        stated = _STATED_VERSION.findall(self.text)
        self.assertTrue(stated, "BASELINE.md states no `Version (`VERSION`)` value")
        for value in stated:
            self.assertEqual(
                value,
                self.live_version,
                f"BASELINE version {value!r} != VERSION file {self.live_version!r}",
            )

    def test_module_count_matches_live_suite(self) -> None:
        counts = _counts(self.text, _MODULE_COUNTS)
        self.assertTrue(counts, "BASELINE.md states no module count")
        live = _live_modules()
        for count in counts:
            self.assertEqual(
                live,
                count,
                f"BASELINE module count {count} != live test modules {live} — "
                "adding or removing a test module requires updating the "
                "BASELINE.md 82/677 counts in the SAME change "
                "(see BASELINE.md 'Same-change update rule')",
            )

    def test_function_count_matches_live_discovery(self) -> None:
        counts = _counts(self.text, _FUNCTION_COUNTS)
        self.assertTrue(counts, "BASELINE.md states no function/test-case count")
        live = _live_functions()
        for count in counts:
            self.assertEqual(
                live,
                count,
                f"BASELINE test count {count} != live unittest count {live} — "
                "adding or removing a test requires updating the "
                "BASELINE.md 82/677 counts in the SAME change "
                "(see BASELINE.md 'Same-change update rule')",
            )

    def test_make_check_inventory_matches_makefile_recipe(self) -> None:
        makefile = MAKEFILE.read_text(encoding="utf-8")
        make_commands = _make_target_commands(makefile, "check")
        self.assertTrue(make_commands, "Makefile has no check recipe commands")

        inventory = _section(self.text, "Invariant inventory")
        baseline_commands = _INVENTORY_COMMAND.findall(inventory)
        self.assertEqual(
            baseline_commands,
            make_commands,
            "BASELINE.md invariant inventory must match the Makefile check recipe",
        )

        # Absolute pin of the gate-of-record composition: the relative check above
        # passes even if BOTH the Makefile and BASELINE dropped a sub-step in
        # lockstep, so pin the six documented sub-steps directly -- a dropped or
        # reordered step silently shrinks the regression net and is a regression.
        documented_substeps = [
            "bash scripts/sync.sh --check",
            "bash platforms/claude-code/scripts/validate.sh",
            "bash platforms/cursor/scripts/validate.sh",
            "bash platforms/antigravity/scripts/validate.sh",
            "cd platforms/codex && bash scripts/validate.sh",
            "python3 -m unittest discover -s tests",
        ]
        self.assertEqual(
            make_commands,
            documented_substeps,
            "make check must compose exactly the six documented sub-steps in order "
            "(sync --check, claude-code/cursor/antigravity/codex validators, "
            "unittest discovery); a dropped or reordered sub-step is a regression",
        )

    def test_guard_set_matches_guard_mapping(self) -> None:
        section = _section(self.text, "Guard-to-test mapping")
        mapping_modules = _GUARD_MAPPING_COMMAND.findall(section)
        self.assertTrue(mapping_modules, "BASELINE.md guard mapping lists no test modules")

        fenced = re.search(r"```bash\s*(?P<body>.*?)\s*```", section, re.DOTALL)
        self.assertIsNotNone(fenced, "BASELINE.md guard section has no command block")
        guard_set_modules = _GUARD_SET_COMMAND.findall(fenced.group("body"))
        self.assertEqual(
            guard_set_modules,
            mapping_modules,
            "BASELINE.md guard command block must match the guard mapping table",
        )
        missing = [name for name in mapping_modules if not (TESTS_DIR / f"{name}.py").is_file()]
        self.assertEqual(missing, [], f"BASELINE.md maps missing guard modules: {missing}")


if __name__ == "__main__":
    unittest.main()
