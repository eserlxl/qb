"""Phase 8.2 -- changelog entry-structure governance (standard library only).

Each platform CHANGELOG's latest version section must carry at least one recognized
`### <Added|Changed|Deprecated|Removed|Fixed|Security>` subsection with a real,
non-placeholder bullet, so an empty or placeholder release note can never be
committed. Keep-a-Changelog format.
"""

from __future__ import annotations

import re
import unittest

from tests.qb_monorepo import ALL_PACKAGES, REPO_ROOT

_VERSION_HEADER = re.compile(r"^## \[[0-9]+\.[0-9]+\.[0-9]+\]", re.MULTILINE)
_RECOGNIZED_SECTIONS = ("Added", "Changed", "Deprecated", "Removed", "Fixed", "Security")
_SUBSECTION = re.compile(r"^### (" + "|".join(_RECOGNIZED_SECTIONS) + r")\s*$")
# Placeholder bullet contents that must NOT count as a real release-note entry.
_PLACEHOLDERS = {"", "-", "tbd", "todo", "n/a", "none", "version bump", "version bump."}


def _latest_section(text: str) -> str:
    matches = list(_VERSION_HEADER.finditer(text))
    if not matches:
        return ""
    start = matches[0].start()
    end = matches[1].start() if len(matches) > 1 else len(text)
    return text[start:end]


def _real_bullet(line: str) -> bool:
    stripped = line.lstrip()
    if not stripped.startswith("- "):
        return False
    content = stripped[2:].strip()
    return content.lower() not in _PLACEHOLDERS and len(content) >= 3


class ChangelogGovernanceTest(unittest.TestCase):
    def test_latest_section_has_a_real_recognized_subsection(self):
        root_version = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
        for pkg in ALL_PACKAGES:
            changelog = pkg["root"] / "CHANGELOG.md"
            self.assertTrue(changelog.is_file(), f"missing changelog: {changelog}")
            section = _latest_section(changelog.read_text(encoding="utf-8"))
            self.assertTrue(section, f"no '## [x.y.z]' version section in {changelog}")
            self.assertTrue(
                section.startswith(f"## [{root_version}]"),
                f"{changelog} latest section is not for root VERSION {root_version}",
            )
            self.assertTrue(
                any(_SUBSECTION.match(line) for line in section.splitlines()),
                f"{changelog} latest version section has no recognized "
                f"### <{'|'.join(_RECOGNIZED_SECTIONS)}> subsection")
            # At least one recognized subsection must carry a real (non-placeholder) bullet.
            in_recognized = False
            has_real = False
            for line in section.splitlines():
                if _SUBSECTION.match(line):
                    in_recognized = True
                    continue
                if line.startswith("### "):       # an unrecognized subsection
                    in_recognized = False
                    continue
                if in_recognized and _real_bullet(line):
                    has_real = True
                    break
            self.assertTrue(
                has_real,
                f"{changelog} latest version section has no non-placeholder bullet "
                f"under a recognized ### subsection")


if __name__ == "__main__":
    unittest.main()
