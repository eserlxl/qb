"""Phase 8.5 -- release-runbook consistency (standard library only).

Pins RELEASING.md to the tooling it documents: every `make <target>` it names (in a
code span) must be a real Makefile target, and the sanctioned bump path it names must
exist -- so the documented release procedure cannot drift from the commands that
implement it.
"""

from __future__ import annotations

import re
import unittest

from tests.qb_monorepo import REPO_ROOT

RELEASING = REPO_ROOT / "RELEASING.md"
MAKEFILE = REPO_ROOT / "Makefile"
BUMP = REPO_ROOT / "scripts/bump-version.sh"

_MAKE_TARGET_DEF = re.compile(r"^([a-zA-Z][a-zA-Z0-9_-]*):", re.MULTILINE)
_MAKE_REF = re.compile(r"\bmake\s+([a-zA-Z][a-zA-Z0-9_-]*)")


def _code_spans(text: str) -> str:
    # Only inspect fenced code blocks and inline-code spans, so prose like "make
    # sure" never reads as a Makefile-target reference.
    spans = re.findall(r"```.*?```", text, re.DOTALL)
    spans += re.findall(r"`[^`]+`", text)
    return "\n".join(spans)


class ReleaseDocsTest(unittest.TestCase):
    def _read(self, path):
        self.assertTrue(path.is_file(), f"missing doc: {path}")
        return path.read_text(encoding="utf-8")

    def test_releasing_doc_exists(self):
        self.assertTrue(RELEASING.is_file(), "RELEASING.md missing")

    def test_make_targets_referenced_are_real(self):
        real_targets = set(_MAKE_TARGET_DEF.findall(self._read(MAKEFILE)))
        self.assertTrue(real_targets, "no Makefile targets parsed")
        referenced = set(_MAKE_REF.findall(_code_spans(self._read(RELEASING))))
        self.assertTrue(referenced, "RELEASING.md references no 'make <target>'")
        missing = sorted(t for t in referenced if t not in real_targets)
        self.assertEqual(missing, [],
                         f"RELEASING.md names non-existent Make targets: {missing}")
        # the release procedure must name the gate and the sanitized-export build
        self.assertIn("check", referenced)
        self.assertIn("export-sanitized", referenced)

    def test_bump_path_referenced_and_exists(self):
        self.assertIn("scripts/bump-version.sh", self._read(RELEASING),
                      "RELEASING.md must name the sanctioned bump path")
        self.assertTrue(BUMP.is_file(), "scripts/bump-version.sh missing")


if __name__ == "__main__":
    unittest.main()
