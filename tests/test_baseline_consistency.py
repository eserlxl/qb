"""Guard: BASELINE.md stays consistent with the live tree.

BASELINE.md is the committed gate-of-record reference, but nothing derived its
stated version or test-suite counts from the source of truth, so it silently
drifted after the tree moved forward. This guard pins it the same way
``tests/test_doc_consistency.py`` pins the README: every value BASELINE asserts
is re-derived from the live tree and compared.

Semantics:

* the stated **version** must equal the root ``VERSION`` file exactly, and
* the live module / test-case counts must equal every count BASELINE states, so
  adding or removing tests requires updating the committed baseline reference.

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
                live, count, f"BASELINE module count {count} != live test modules {live}"
            )

    def test_function_count_matches_live_discovery(self) -> None:
        counts = _counts(self.text, _FUNCTION_COUNTS)
        self.assertTrue(counts, "BASELINE.md states no function/test-case count")
        live = _live_functions()
        for count in counts:
            self.assertEqual(
                live, count, f"BASELINE test count {count} != live unittest count {live}"
            )


if __name__ == "__main__":
    unittest.main()
