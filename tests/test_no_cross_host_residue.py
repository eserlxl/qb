"""No cross-host residue in any platform's hand-authored host files.

Scope: ONLY hand-authored host files are scanned -- each skill's ``SKILL.md``
orchestration, slash commands, and agents (Claude Code ``agents/*.md`` and the
Codex ``agents/openai.yaml``). The synced, host-neutral planner specs,
reference docs, and validator (which say only "QB") are intentionally exempt and
are NOT scanned here. README / CHANGELOG / docs are likewise out of scope -- they
may mention all three platforms and the upstream attribution.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from tests.qb_monorepo import CLAUDE_CODE, CODEX, CURSOR


def _hand_authored_host_files(skills_root: Path, components_roots: list[Path]) -> list[Path]:
    """Collect a platform's hand-authored host files.

    - every ``SKILL.md`` under ``skills_root`` (skill orchestration)
    - every ``*.md`` directly under each commands/agents root
    - any ``openai.yaml`` (Codex agent manifest) under those roots or skills

    The co-located planner specs inside skill directories (e.g.
    ``second-planner.md``) are synced neutral content and are deliberately
    excluded by only picking ``SKILL.md`` from the skills tree.
    """
    files: list[Path] = []
    if skills_root.exists():
        files += sorted(skills_root.rglob("SKILL.md"))
        files += sorted(skills_root.rglob("openai.yaml"))
    for root in components_roots:
        if root.exists():
            files += sorted(root.glob("*.md"))
            files += sorted(root.rglob("openai.yaml"))
    # De-duplicate while preserving order.
    seen: set[Path] = set()
    unique: list[Path] = []
    for f in files:
        if f not in seen:
            seen.add(f)
            unique.append(f)
    return unique


class CrossHostResidueTests(unittest.TestCase):
    def _assert_clean(self, platform: dict, host_root: Path) -> None:
        if not platform["manifest"].exists():
            self.skipTest(f"platform not built yet: {platform['id']}")

        files = _hand_authored_host_files(
            host_root / "skills",
            [host_root / "commands", host_root / "agents"],
        )
        self.assertTrue(
            files,
            f"expected to find hand-authored host files for {platform['id']} under {host_root}",
        )

        problems: list[str] = []
        for path in files:
            text = path.read_text(encoding="utf-8")
            for needle in platform["forbidden"]:
                if needle in text:
                    problems.append(f"cross_host_residue={path}::token={needle!r}")
        self.assertEqual(problems, [], "\n".join(problems))

    def test_claude_code_host_files_have_no_cross_host_residue(self) -> None:
        self._assert_clean(CLAUDE_CODE, CLAUDE_CODE["root"])

    def test_cursor_host_files_have_no_cross_host_residue(self) -> None:
        self._assert_clean(CURSOR, CURSOR["root"])

    def test_codex_host_files_have_no_cross_host_residue(self) -> None:
        # Codex packages its host files under plugins/codexqb/.
        self._assert_clean(CODEX, CODEX["root"] / "plugins/codexqb")


if __name__ == "__main__":
    unittest.main()
