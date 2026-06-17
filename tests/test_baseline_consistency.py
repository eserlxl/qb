"""Guard: BASELINE.md stays consistent with the live tree.

BASELINE.md is the committed gate-of-record reference, but nothing derived its
stated version or test-suite counts from the source of truth, so it silently
drifted (it advertised v0.14.1 / 44 modules / 324 functions long after the tree
moved to 0.15.0 / 69 / 469). This guard pins it the same way
``tests/test_doc_consistency.py`` pins the README: every value BASELINE asserts
is re-derived from the live tree and compared.

Semantics, matching BASELINE's own wording ("a run reporting *fewer than* N
modules ... is a regression"):

* the stated **version** must equal the root ``VERSION`` file exactly, and
* the live module / function counts must be **at least** every floor BASELINE
  states (so adding tests never fails this guard, but dropping below the
  recorded floor — or letting VERSION and BASELINE diverge — does).

Standard library only, like the rest of the suite.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.qb_monorepo import REPO_ROOT

BASELINE = REPO_ROOT / "BASELINE.md"
VERSION_FILE = REPO_ROOT / "VERSION"
TESTS_DIR = REPO_ROOT / "tests"

_STATED_VERSION = re.compile(r"Version \(`VERSION`\)\s*\|\s*`(\d+\.\d+\.\d+)`")
# Every place BASELINE states a module-count floor.
_MODULE_FLOORS = (
    re.compile(r"Test modules \(`tests/test_\*\.py`\)\s*\|\s*(\d+)"),
    re.compile(r"Expected test modules\s*\|\s*(\d+)"),
    re.compile(r"\((\d+) modules / \d+ functions\)"),
    re.compile(r"fewer than (\d+) modules"),
)
# Every place BASELINE states a function-count floor.
_FUNCTION_FLOORS = (
    re.compile(r"^\| Test functions\s*\|\s*(\d+)", re.MULTILINE),
    re.compile(r"Expected test functions\s*\|\s*(\d+)"),
    re.compile(r"\(\d+ modules / (\d+) functions\)"),
    re.compile(r"fewer than \d+ modules or fewer than (\d+) passing functions"),
)


def _live_modules() -> int:
    return len(list(TESTS_DIR.glob("test_*.py")))


def _live_functions() -> int:
    # Substring count of test-method definitions: matches `unittest discover`'s
    # reported count for this suite, catches `async def test_*` too, and can only
    # over-count (the safe direction for a `live >= floor` assertion).
    total = 0
    for path in TESTS_DIR.glob("test_*.py"):
        total += path.read_text(encoding="utf-8").count("def test_")
    return total


def _floors(text: str, patterns) -> list[int]:
    found: list[int] = []
    for rx in patterns:
        found.extend(int(m) for m in rx.findall(text))
    return found


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

    def test_module_count_floor_met(self) -> None:
        floors = _floors(self.text, _MODULE_FLOORS)
        self.assertTrue(floors, "BASELINE.md states no module-count floor")
        live = _live_modules()
        for floor in floors:
            self.assertGreaterEqual(
                live, floor, f"only {live} test modules, below BASELINE floor {floor}"
            )

    def test_function_count_floor_met(self) -> None:
        floors = _floors(self.text, _FUNCTION_FLOORS)
        self.assertTrue(floors, "BASELINE.md states no function-count floor")
        live = _live_functions()
        for floor in floors:
            self.assertGreaterEqual(
                live, floor, f"only {live} test functions, below BASELINE floor {floor}"
            )


if __name__ == "__main__":
    unittest.main()
